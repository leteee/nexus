"""Runtime context passed to nodes."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import EngineSettings
from .models import RunEvent, StepResult
from .utils import utc_now

if TYPE_CHECKING:  # pragma: no cover
    from .engine import Engine
    from .models import RunResult


class StepView(dict[str, Any]):
    """Read-only-ish view of a completed step exposed to expressions.

    Output keys are available both directly (``steps.load.data``) and through
    the ``outputs`` mapping (``steps.load.outputs.data``).  Metadata keys win
    over same-named outputs so ``status``/``error`` are always reliable.
    """

    def __init__(self, result: StepResult) -> None:
        outputs = dict(result.outputs)
        metadata = {
            "id": result.id,
            "status": result.status.value,
            "error": result.error,
            "attempts": result.attempts,
            "duration_ms": result.duration_ms,
            "outputs": outputs,
        }
        super().__init__({**outputs, **metadata})
        self._result = result

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    @property
    def ok(self) -> bool:
        return self._result.ok

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"StepView(id={self['id']!r}, status={self['status']!r}, keys={sorted(self['outputs'])})"


EventListener = Callable[[RunEvent], None]


@dataclass
class NodeContext:
    """Execution context for a single node invocation."""

    run_id: str
    flow_name: str
    flow_path: Path
    step_id: str
    attempt: int
    project_root: Path
    workdir: Path
    settings: EngineSettings
    scope: Mapping[str, Any]
    engine: Engine
    logger: logging.Logger
    subflow_stack: tuple[str, ...] = ()
    event_listener: EventListener | None = field(default=None, repr=False)
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- convenience accessors -------------------------------------------

    @property
    def vars(self) -> Mapping[str, Any]:
        value = self.scope.get("vars", {})
        return value if isinstance(value, Mapping) else {}

    @property
    def steps(self) -> Mapping[str, Any]:
        value = self.scope.get("steps", {})
        return value if isinstance(value, Mapping) else {}

    @property
    def config(self) -> Mapping[str, Any]:
        value = self.scope.get("config", {})
        return value if isinstance(value, Mapping) else {}

    @property
    def env(self) -> Mapping[str, Any]:
        value = self.scope.get("env", {})
        return value if isinstance(value, Mapping) else {}

    # -- paths ------------------------------------------------------------

    def path(self, value: str | Path, *, base: Path | None = None) -> Path:
        """Resolve *value* relative to the run working directory by default."""

        path = Path(os.path.expandvars(os.path.expanduser(str(value))))
        if path.is_absolute():
            return path.resolve()
        return ((base or self.workdir) / path).resolve()

    def project_path(self, value: str | Path) -> Path:
        return self.path(value, base=self.project_root)

    def ensure_dir(self, value: str | Path, *, base: Path | None = None) -> Path:
        path = self.path(value, base=base)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -- observability ----------------------------------------------------

    def emit(self, event_type: str, **data: Any) -> None:
        if self.event_listener is None:
            return
        self.event_listener(
            RunEvent(
                type=event_type,
                timestamp=utc_now(),
                run_id=self.run_id,
                flow=self.flow_name,
                step=self.step_id,
                data=data,
            )
        )

    def log(self, level: int, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.log(level, message, *args, **kwargs)

    # -- composition ------------------------------------------------------

    def run_flow(
        self,
        flow: str | Path,
        *,
        workdir: str | Path | None = None,
        variables: Mapping[str, Any] | None = None,
        inputs: Mapping[str, Any] | None = None,
        inherit_vars: bool = False,
    ) -> RunResult:
        """Execute a child flow using the current engine and registry."""

        child_workdir = self.path(workdir) if workdir is not None else self.workdir
        return self.engine.run_subflow(
            flow,
            parent=self,
            workdir=child_workdir,
            variables=dict(variables or {}),
            inputs=dict(inputs or {}),
            inherit_vars=inherit_vars,
        )
