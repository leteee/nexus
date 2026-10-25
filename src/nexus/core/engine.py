"""Flow execution engine and scheduler.

The engine turns a validated :class:`~nexus.core.models.FlowSpec` into a run:

* steps are scheduled according to the DAG (explicit ``needs`` + implicit
  ``steps.<id>`` references)
* ``sequential`` mode additionally enforces declaration order
* ready steps may run in parallel (``execution.max_workers``)
* ``when``, ``foreach``, retry, timeout and ``on_error`` are handled per step
* outputs are passed explicitly through expressions, never via hidden state
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import random
import threading
import time
import traceback
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import EngineSettings, load_settings, resolve_flow_path
from .context import EventListener, NodeContext, StepView
from .errors import (
    ExpressionError,
    FlowError,
    NodeLoadError,
    StepExecutionError,
    SubflowError,
)
from .expr import ExpressionResolver
from .graph import FlowGraph, build_graph
from .loader import load_flow_file, validate_flow
from .models import (
    ExecutionSettings,
    FlowSpec,
    RunEvent,
    RunResult,
    RunStatus,
    StepResult,
    StepSpec,
    StepStatus,
)
from .registry import NodeRegistry, default_registry
from .utils import deep_merge, duration_ms, jsonable, utc_now

logger = logging.getLogger(__name__)


@dataclass
class _RunState:
    """Mutable state shared by the scheduler and expression scopes."""

    base_scope: dict[str, Any]
    steps: dict[str, StepResult] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "steps": {step_id: StepView(result) for step_id, result in self.steps.items()},
            }

    def record(self, result: StepResult) -> None:
        with self.lock:
            self.steps[result.id] = result

    def final_steps(self, order: list[str]) -> dict[str, StepResult]:
        with self.lock:
            return {step_id: self.steps[step_id] for step_id in order if step_id in self.steps}


class Engine:
    """Load, validate and execute Nexus flows."""

    def __init__(
        self,
        *,
        project_root: Path | str | None = None,
        settings: EngineSettings | None = None,
        registry: NodeRegistry | None = None,
        event_listener: EventListener | None = None,
        load_nodes: bool = True,
    ) -> None:
        self.settings = settings or load_settings(project_root)
        self.registry = registry or default_registry
        self.event_listener = event_listener
        if load_nodes:
            self._ensure_nodes()

    # ------------------------------------------------------------------
    # Node loading
    # ------------------------------------------------------------------

    def _ensure_nodes(self) -> None:
        try:
            self.registry.load_all(
                modules=self.settings.node_modules,
                entry_points_enabled=self.settings.load_entry_points,
            )
        except NodeLoadError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise NodeLoadError("engine", f"{type(exc).__name__}: {exc}") from exc

    # ------------------------------------------------------------------
    # Loading / planning
    # ------------------------------------------------------------------

    def load_flow(self, flow: FlowSpec | str | Path) -> tuple[FlowSpec, Path]:
        if isinstance(flow, FlowSpec):
            return flow, Path(f"<memory:{flow.name or 'flow'}>")
        path = resolve_flow_path(self.settings, flow)
        return load_flow_file(path), path

    def plan(self, flow: FlowSpec | str | Path) -> FlowGraph:
        spec, _path = self.load_flow(flow)
        spec = self._apply_execution(spec)
        validate_flow(spec, self.registry, raise_on_error=True)
        return build_graph(spec)

    def validate(self, flow: FlowSpec | str | Path) -> list[str]:
        spec, _path = self.load_flow(flow)
        spec = self._apply_execution(spec)
        return validate_flow(spec, self.registry, raise_on_error=False)

    def _apply_execution(
        self,
        flow: FlowSpec,
        overrides: Mapping[str, Any] | ExecutionSettings | None = None,
    ) -> FlowSpec:
        """Merge engine defaults < explicit flow settings < run overrides."""

        base = self.settings.execution.model_dump()
        explicit = {
            field: getattr(flow.execution, field)
            for field in flow.execution.model_fields_set
        }
        if isinstance(overrides, ExecutionSettings):
            override_data = overrides.model_dump(exclude_unset=True)
        else:
            override_data = {
                key: value for key, value in dict(overrides or {}).items() if value is not None
            }
        effective = ExecutionSettings.model_validate({**base, **explicit, **override_data})
        if effective == flow.execution:
            return flow
        return flow.model_copy(update={"execution": effective}, deep=True)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(
        self,
        flow: FlowSpec | str | Path,
        *,
        workdir: Path | str | None = None,
        variables: Mapping[str, Any] | None = None,
        inputs: Mapping[str, Any] | None = None,
        dry_run: bool = False,
        run_id: str | None = None,
        execution: Mapping[str, Any] | ExecutionSettings | None = None,
        _parent: NodeContext | None = None,
        _inherit_vars: bool = False,
        _subflow_stack: tuple[str, ...] = (),
    ) -> RunResult:
        """Execute a flow and return a structured result.

        ``workdir`` defaults to ``settings.workdir`` or the current directory.
        Relative paths used by nodes are resolved against this directory.
        """

        spec, flow_path = self.load_flow(flow)
        spec = self._apply_execution(spec, execution)
        validate_flow(spec, self.registry, raise_on_error=True)
        graph = build_graph(spec)

        if workdir is None:
            workdir_path = (self.settings.workdir or Path.cwd()).resolve()
        else:
            workdir_path = Path(workdir).expanduser()
            if not workdir_path.is_absolute():
                workdir_path = (Path.cwd() / workdir_path).resolve()
            else:
                workdir_path = workdir_path.resolve()
        workdir_path.mkdir(parents=True, exist_ok=True)

        run_id = run_id or uuid.uuid4().hex[:12]
        started = utc_now()
        parent_vars = dict(_parent.vars) if (_parent and _inherit_vars) else {}
        merged_vars = {**parent_vars, **dict(variables or {})}

        scope, resolved_inputs = self._build_scope(
            spec,
            run_id=run_id,
            flow_path=flow_path,
            workdir=workdir_path,
            variables=merged_vars,
            inputs=inputs,
            dry_run=dry_run,
            started=started,
            parent=_parent,
        )

        self._emit(run_id, spec.name or "flow", "run_started", flow=str(flow_path), workdir=str(workdir_path))
        logger.info("Run %s started: %s (%d steps, %s)", run_id, spec.name, len(spec.steps), spec.execution.strategy)

        state = _RunState(base_scope=scope)
        metadata = {
            "flow_path": str(flow_path),
            "workdir": str(workdir_path),
            "strategy": spec.execution.strategy,
            "max_workers": 1 if spec.execution.strategy == "sequential" else spec.execution.max_workers,
            "dry_run": dry_run,
            "inputs": resolved_inputs,
        }

        if dry_run:
            for step in spec.steps:
                state.record(
                    StepResult(
                        id=step.id,
                        use=step.use,
                        status=StepStatus.SKIPPED,
                        error="dry run: not executed",
                        started_at=started,
                        finished_at=started,
                    )
                )
            finished = utc_now()
            result = RunResult(
                run_id=run_id,
                flow=spec.name or "flow",
                status=RunStatus.SUCCESS,
                started_at=started,
                finished_at=finished,
                duration_ms=duration_ms(started, finished),
                steps=state.final_steps(graph.order),
                outputs={},
                metadata=metadata,
            )
            self._emit(run_id, spec.name or "flow", "run_finished", status=result.status.value, dry_run=True)
            return result

        cancelled = False
        cancel_reason: str | None = None
        workers = 1 if spec.execution.strategy == "sequential" else spec.execution.max_workers
        pending: set[str] = set(graph.order)
        running: dict[Future[tuple[StepResult, bool]], str] = {}

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"nexus-{run_id}") as pool:
            while pending or running:
                if not cancelled:
                    for step_id in graph.order:
                        if step_id not in pending:
                            continue
                        if len(running) >= workers:
                            break
                        if not graph.dependencies[step_id].issubset(state.steps.keys()):
                            continue
                        pending.remove(step_id)
                        step = graph.steps[step_id]
                        future = pool.submit(
                            self._execute_step, step, spec, state, run_id, flow_path, _subflow_stack
                        )
                        running[future] = step_id

                if not running:
                    if pending:
                        # This should be impossible after graph validation; fail
                        # loudly instead of hanging forever.
                        raise FlowError(
                            f"cannot schedule steps {sorted(pending)}; dependency graph is inconsistent"
                        )
                    break

                done, _ = wait(running.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    step_id = running.pop(future)
                    try:
                        step_result, fatal = future.result()
                    except Exception as exc:  # pragma: no cover - _execute_step catches
                        step_result = self._failed_result(
                            graph.steps[step_id], 1, exc, started=utc_now(), finished=utc_now()
                        )
                        fatal = graph.steps[step_id].on_error == "fail"
                    state.record(step_result)
                    self._log_step_result(step_result)

                    if fatal and spec.execution.fail_fast and not cancelled:
                        cancelled = True
                        cancel_reason = f"step '{step_id}' failed"

                if cancelled:
                    for step_id in list(pending):
                        step = graph.steps[step_id]
                        now = utc_now()
                        state.record(
                            StepResult(
                                id=step.id,
                                use=step.use,
                                status=StepStatus.CANCELLED,
                                error=f"not executed: {cancel_reason}",
                                started_at=now,
                                finished_at=now,
                            )
                        )
                    pending.clear()

        final_steps = state.final_steps(graph.order)
        finished = utc_now()

        run_error: str | None
        failed = [result for result in final_steps.values() if result.status == StepStatus.FAILED]
        if failed:
            run_status = RunStatus.FAILED
            first_error = failed[0].error or f"step '{failed[0].id}' failed"
            run_error = first_error
        elif cancelled:
            run_status = RunStatus.CANCELLED
            run_error = cancel_reason
        else:
            run_status = RunStatus.SUCCESS
            run_error = None

        outputs: dict[str, Any] = {}
        output_error: str | None = None
        try:
            outputs = self._resolve_outputs(spec, state)
        except Exception as exc:
            output_error = f"{type(exc).__name__}: {exc}"
            if run_status is RunStatus.SUCCESS:
                run_status = RunStatus.FAILED
                run_error = f"failed to resolve flow outputs: {output_error}"
            logger.error("Failed to resolve flow outputs: %s", exc)

        result = RunResult(
            run_id=run_id,
            flow=spec.name or "flow",
            status=run_status,
            started_at=started,
            finished_at=finished,
            duration_ms=duration_ms(started, finished),
            steps=final_steps,
            outputs=outputs,
            error=run_error or output_error,
            metadata=metadata,
        )
        self._emit(
            run_id,
            spec.name or "flow",
            "run_finished",
            status=result.status.value,
            duration_ms=result.duration_ms,
            error=result.error,
        )
        logger.info(
            "Run %s finished: %s in %.1fms",
            run_id,
            result.status.value,
            result.duration_ms,
        )
        return result

    def run_subflow(
        self,
        flow: FlowSpec | str | Path,
        *,
        parent: NodeContext,
        workdir: Path | str | None = None,
        variables: Mapping[str, Any] | None = None,
        inputs: Mapping[str, Any] | None = None,
        inherit_vars: bool = False,
    ) -> RunResult:
        if isinstance(flow, (str, Path)) and not Path(flow).is_absolute():
            local = parent.flow_path.parent / flow
            if local.is_file():
                flow = local
        spec, flow_path = self.load_flow(flow)
        stack = (*parent.subflow_stack, str(flow_path))
        if len(stack) > self.settings.max_subflow_depth:
            raise SubflowError(
                f"subflow depth exceeded ({self.settings.max_subflow_depth}); stack: {' -> '.join(stack)}"
            )
        if str(flow_path) in parent.subflow_stack:
            raise SubflowError(f"recursive subflow detected: {flow_path}")

        child_vars = dict(parent.vars) if inherit_vars else {}
        child_vars.update(dict(variables or {}))
        return self.run(
            spec,
            workdir=workdir or parent.workdir,
            variables=child_vars,
            inputs=inputs,
            _parent=parent,
            _inherit_vars=inherit_vars,
            _subflow_stack=stack,
        )

    # ------------------------------------------------------------------
    # Scope / variables
    # ------------------------------------------------------------------

    def _build_scope(
        self,
        flow: FlowSpec,
        *,
        run_id: str,
        flow_path: Path,
        workdir: Path,
        variables: Mapping[str, Any],
        inputs: Mapping[str, Any] | None,
        dry_run: bool,
        started: Any,
        parent: NodeContext | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        env = dict(os.environ)
        settings_scope = self.settings.scope()
        run_scope = {
            "id": run_id,
            "flow": flow.name or "flow",
            "flow_path": str(flow_path),
            "workdir": str(workdir),
            "project_root": str(self.settings.project_root),
            "started_at": started.isoformat(),
            "dry_run": dry_run,
            "parent_run_id": parent.run_id if parent else None,
        }

        raw_inputs = deep_merge(flow.inputs, inputs or {})
        base_scope: dict[str, Any] = {
            "env": env,
            "settings": settings_scope,
            "run": run_scope,
            "inputs": raw_inputs,
        }
        resolved_inputs = ExpressionResolver({**base_scope, "vars": {}}).resolve(raw_inputs)
        base_scope["inputs"] = resolved_inputs

        flow_vars: dict[str, Any] = {}
        var_scope = {**base_scope, "vars": flow_vars}
        resolver = ExpressionResolver(var_scope)
        for key, value in flow.vars.items():
            flow_vars[key] = resolver.resolve(value)
        for key, value in variables.items():
            flow_vars[key] = resolver.resolve(value)
        base_scope["vars"] = flow_vars

        config_scope = ExpressionResolver({**base_scope, "config": {}}).resolve(dict(flow.config))
        base_scope["config"] = config_scope
        base_scope["settings"] = settings_scope
        base_scope["steps"] = {}
        return base_scope, resolved_inputs

    def _resolve_outputs(self, flow: FlowSpec, state: _RunState) -> dict[str, Any]:
        if not flow.outputs:
            return {}
        scope = {**state.base_scope, **state.snapshot()}
        resolver = ExpressionResolver(scope)
        return {key: resolver.resolve(value) for key, value in flow.outputs.items()}

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        step: StepSpec,
        flow: FlowSpec,
        state: _RunState,
        run_id: str,
        flow_path: Path,
        subflow_stack: tuple[str, ...] = (),
    ) -> tuple[StepResult, bool]:
        started = utc_now()
        event_scope = {**state.base_scope, **state.snapshot()}
        resolver = ExpressionResolver(event_scope)

        self._emit(run_id, flow.name or "flow", "step_started", step=step.id, use=step.use)

        try:
            if step.when is not None and not resolver.evaluate_condition(step.when):
                finished = utc_now()
                result = StepResult(
                    id=step.id,
                    use=step.use,
                    status=StepStatus.SKIPPED,
                    error="when condition evaluated to false",
                    started_at=started,
                    finished_at=finished,
                    duration_ms=duration_ms(started, finished),
                )
                self._emit(run_id, flow.name or "flow", "step_skipped", step=step.id)
                return result, False

            if step.foreach is not None:
                raw_items = resolver.evaluate_items(step.foreach.items if hasattr(step.foreach, "items") else step.foreach)
                item_name = getattr(step.foreach, "item_name", "item")
                index_name = getattr(step.foreach, "index_name", "index")
                concurrency = getattr(step.foreach, "concurrency", 1)
                outputs, attempts = self._execute_foreach(
                    step,
                    flow,
                    state,
                    run_id,
                    flow_path,
                    subflow_stack,
                    raw_items,
                    item_name=item_name,
                    index_name=index_name,
                    concurrency=concurrency,
                )
            else:
                raw, attempts = self._invoke_with_retry(
                    step, flow, state, run_id, flow_path, event_scope, subflow_stack
                )
                outputs = self._select_outputs(step, raw)

            finished = utc_now()
            result = StepResult(
                id=step.id,
                use=step.use,
                status=StepStatus.SUCCESS,
                outputs=outputs,
                attempts=attempts,
                started_at=started,
                finished_at=finished,
                duration_ms=duration_ms(started, finished),
            )
            self._emit(
                run_id,
                flow.name or "flow",
                "step_finished",
                step=step.id,
                status=result.status.value,
                duration_ms=result.duration_ms,
            )
            return result, False
        except Exception as exc:
            finished = utc_now()
            result = self._failed_result(step, getattr(exc, "attempts", 0), exc, started=started, finished=finished)
            if step.on_error == "continue":
                logger.warning("Step '%s' failed and will continue: %s", step.id, exc)
                self._emit(
                    run_id,
                    flow.name or "flow",
                    "step_finished",
                    step=step.id,
                    status=result.status.value,
                    error=result.error,
                )
                return result, False
            self._emit(
                run_id,
                flow.name or "flow",
                "step_finished",
                step=step.id,
                status=result.status.value,
                error=result.error,
            )
            return result, True

    def _execute_foreach(
        self,
        step: StepSpec,
        flow: FlowSpec,
        state: _RunState,
        run_id: str,
        flow_path: Path,
        subflow_stack: tuple[str, ...],
        items: list[Any],
        *,
        item_name: str,
        index_name: str,
        concurrency: int,
    ) -> tuple[dict[str, Any], int]:
        if not items:
            return {"items": [], "count": 0}, 0

        def run_one(index_item: tuple[int, Any]) -> tuple[dict[str, Any], int]:
            index, item = index_item
            scope = {**state.base_scope, **state.snapshot(), item_name: item, index_name: index}
            raw, attempts = self._invoke_with_retry(
                step, flow, state, run_id, flow_path, scope, subflow_stack
            )
            return self._select_outputs(step, raw), attempts

        indexed = list(enumerate(items))
        if concurrency <= 1 or len(indexed) <= 1:
            results = [run_one(index_item) for index_item in indexed]
        else:
            workers = min(concurrency, len(indexed))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"nexus-{run_id}-foreach") as pool:
                results = list(pool.map(run_one, indexed))

        attempts = max((attempt for _outputs, attempt in results), default=0)
        return {
            "items": [outputs for outputs, _attempt in results],
            "count": len(results),
        }, attempts

    def _invoke_with_retry(
        self,
        step: StepSpec,
        flow: FlowSpec,
        state: _RunState,
        run_id: str,
        flow_path: Path,
        scope: Mapping[str, Any],
        subflow_stack: tuple[str, ...] = (),
    ) -> tuple[Any, int]:
        policy = step.retry_policy
        attempts = max(1, policy.max_attempts)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return (
                    self._invoke_node(step, flow, state, run_id, flow_path, scope, attempt, subflow_stack),
                    attempt,
                )
            except Exception as exc:  # noqa: BLE001 - re-raised after retries
                last_error = exc
                if attempt >= attempts:
                    break
                delay = min(policy.delay_s * (policy.backoff ** (attempt - 1)), policy.max_delay_s)
                if policy.jitter_s > 0:
                    delay += random.uniform(0.0, policy.jitter_s)
                self._emit(
                    run_id,
                    flow.name or "flow",
                    "step_retry",
                    step=step.id,
                    attempt=attempt,
                    delay_s=delay,
                    error=f"{type(exc).__name__}: {exc}",
                )
                logger.warning(
                    "Step '%s' attempt %d/%d failed (%s); retrying in %.2fs",
                    step.id,
                    attempt,
                    attempts,
                    exc,
                    delay,
                )
                if delay > 0:
                    time.sleep(delay)
        assert last_error is not None
        last_error.attempts = attempts  # type: ignore[attr-defined]
        raise last_error

    def _invoke_node(
        self,
        step: StepSpec,
        flow: FlowSpec,
        state: _RunState,
        run_id: str,
        flow_path: Path,
        scope: Mapping[str, Any],
        attempt: int,
        subflow_stack: tuple[str, ...] = (),
    ) -> Any:
        spec = self.registry.get(step.use)
        resolver = ExpressionResolver(scope)
        try:
            raw_inputs = resolver.resolve(step.inputs)
        except ExpressionError as exc:
            raise StepExecutionError(step.id, f"failed to resolve inputs: {exc}") from exc

        try:
            inputs = spec.validate_inputs(raw_inputs)
        except ValidationError as exc:
            raise StepExecutionError(step.id, f"invalid inputs for node '{step.use}': {exc}") from exc
        except Exception as exc:
            raise StepExecutionError(step.id, f"invalid inputs for node '{step.use}': {exc}") from exc

        context = NodeContext(
            run_id=run_id,
            flow_name=flow.name or "flow",
            flow_path=flow_path,
            step_id=step.id,
            attempt=attempt,
            project_root=self.settings.project_root,
            workdir=Path(scope["run"]["workdir"]),
            settings=self.settings,
            scope=scope,
            engine=self,
            logger=logging.getLogger(f"nexus.flow.{flow.name}.{step.id}"),
            event_listener=self.event_listener,
            subflow_stack=subflow_stack,
        )
        timeout = step.timeout_s or flow.execution.step_timeout_s or self.settings.execution.step_timeout_s

        logger.debug("Invoking node %s for step %s (attempt %d)", step.use, step.id, attempt)
        if spec.is_async:
            return self._call_async(spec.func(context, inputs), timeout, step.id)
        if timeout:
            result = self._call_with_timeout(spec.func, context, inputs, timeout, step.id)
        else:
            result = spec.func(context, inputs)
        if inspect.isawaitable(result):
            return self._call_async(result, None, step.id)
        return result

    @staticmethod
    def _call_async(awaitable: Any, timeout: float | None, step_id: str) -> Any:
        async def runner() -> Any:
            if timeout:
                return await asyncio.wait_for(awaitable, timeout=timeout)
            return await awaitable

        try:
            return asyncio.run(runner())
        except TimeoutError as exc:
            raise StepExecutionError(step_id, f"timed out after {timeout}s") from exc

    @staticmethod
    def _call_with_timeout(func: Callable[..., Any], ctx: NodeContext, inputs: Any, timeout: float, step_id: str) -> Any:
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"nexus-{step_id}-timeout")
        future = pool.submit(func, ctx, inputs)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise StepExecutionError(step_id, f"timed out after {timeout}s") from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------
    # Output handling
    # ------------------------------------------------------------------

    def _select_outputs(self, step: StepSpec, raw: Any) -> dict[str, Any]:
        normalized = self._normalize_output(raw)
        if step.outputs is None:
            return normalized
        if isinstance(step.outputs, list):
            selected: dict[str, Any] = {}
            for key in step.outputs:
                selected[key] = self._lookup_output(normalized, key, step.id)
            return selected
        selected = {}
        for alias, key in step.outputs.items():
            selected[alias] = self._lookup_output(normalized, key, step.id)
        return selected

    @staticmethod
    def _normalize_output(raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, Mapping):
            return dict(raw)
        if hasattr(raw, "model_dump") and callable(raw.model_dump):
            value = raw.model_dump()
            return value if isinstance(value, dict) else {"result": value}
        return {"result": raw}

    @staticmethod
    def _lookup_output(outputs: Mapping[str, Any], key: str, step_id: str) -> Any:
        current: Any = outputs
        for part in key.split("."):
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                raise StepExecutionError(
                    step_id,
                    f"output '{key}' not found; available outputs: {', '.join(sorted(outputs)) or '(none)'}",
                )
        return current

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _failed_result(
        step: StepSpec,
        attempts: int,
        exc: BaseException,
        *,
        started: Any,
        finished: Any,
    ) -> StepResult:
        message = f"{type(exc).__name__}: {exc}"
        return StepResult(
            id=step.id,
            use=step.use,
            status=StepStatus.FAILED,
            error=message,
            error_traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            attempts=max(attempts, 1),
            started_at=started,
            finished_at=finished,
            duration_ms=duration_ms(started, finished),
        )

    def _emit(self, run_id: str, flow_name: str, event_type: str, **data: Any) -> None:
        if self.event_listener is None:
            return
        try:
            self.event_listener(
                RunEvent(
                    type=event_type,
                    timestamp=utc_now(),
                    run_id=run_id,
                    flow=flow_name,
                    step=data.pop("step", None),
                    data=jsonable(data),
                )
            )
        except Exception as exc:  # pragma: no cover - listener must not break runs
            logger.warning("event listener failed: %s", exc)

    @staticmethod
    def _log_step_result(result: StepResult) -> None:
        if result.status is StepStatus.SUCCESS:
            logger.info("Step '%s' succeeded in %.1fms", result.id, result.duration_ms)
        elif result.status is StepStatus.SKIPPED:
            logger.info("Step '%s' skipped: %s", result.id, result.error)
        elif result.status is StepStatus.CANCELLED:
            logger.warning("Step '%s' cancelled: %s", result.id, result.error)
        else:
            logger.error("Step '%s' failed: %s", result.id, result.error)

    # ------------------------------------------------------------------
    # Convenience API
    # ------------------------------------------------------------------

    def run_file(self, path: Path | str, **kwargs: Any) -> RunResult:
        return self.run(path, **kwargs)
