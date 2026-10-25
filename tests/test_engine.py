from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus.core.config import EngineSettings
from nexus.core.engine import Engine
from nexus.core.loader import load_flow_dict
from nexus.core.models import RunStatus, StepStatus


def make_engine(tmp_path: Path, **execution: Any) -> Engine:
    settings = EngineSettings(
        project_root=tmp_path,
        node_modules=[],
        load_entry_points=False,
        execution={"strategy": execution.pop("strategy", "sequential"), **execution},
    )
    return Engine(settings=settings)


def run(engine: Engine, data: dict, tmp_path: Path, **kwargs: Any) -> Any:
    flow = load_flow_dict(data, source="test.yaml")
    return engine.run(flow, workdir=tmp_path, **kwargs)


def flow(*steps: dict, **extra: Any) -> dict:
    return {"version": "2.0", "name": "test", "steps": list(steps), **extra}


def test_sequential_order(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {"id": "one", "use": "test.record", "with": {"value": 1}},
            {"id": "two", "use": "test.record", "with": {"value": 2}},
            {"id": "three", "use": "test.record", "with": {"value": 3}},
        ),
        tmp_path,
    )
    assert result.status is RunStatus.SUCCESS
    assert [step.outputs["value"] for step in result.steps.values()] == [1, 2, 3]


def test_dag_runs_ready_steps_concurrently(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, strategy="dag", max_workers=2)
    result = run(
        engine,
        flow(
            {"id": "a", "use": "test.barrier"},
            {"id": "b", "use": "test.barrier"},
            {"id": "join", "use": "core.noop", "needs": ["a", "b"]},
        ),
        tmp_path,
    )
    # Both barrier nodes can only succeed if they run at the same time.
    assert result.status is RunStatus.SUCCESS, result.error


def test_when_skips_step(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {"id": "skipped", "use": "core.echo", "when": False, "with": {"value": 1}},
            {"id": "after", "use": "core.echo", "with": {"value": "ok"}},
        ),
        tmp_path,
    )
    assert result.steps["skipped"].status is StepStatus.SKIPPED
    assert result.steps["after"].status is StepStatus.SUCCESS
    assert result.status is RunStatus.SUCCESS


def test_foreach_aggregates_results(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {
                "id": "each",
                "use": "test.record",
                "foreach": {"items": [1, 2, 3], "as": "n", "index": "i", "concurrency": 2},
                "with": {"value": "${n * 10 + i}"},
            }
        ),
        tmp_path,
    )
    assert result.status is RunStatus.SUCCESS
    assert result.steps["each"].outputs["count"] == 3
    assert [item["value"] for item in result.steps["each"].outputs["items"]] == [10, 21, 32]


def test_retry_until_success(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {
                "id": "flaky",
                "use": "test.flaky",
                "with": {"key": "retry", "succeed_on_attempt": 3},
                "retry": {"max_attempts": 3, "delay_s": 0.0},
            }
        ),
        tmp_path,
    )
    assert result.status is RunStatus.SUCCESS
    assert result.steps["flaky"].attempts == 3
    assert result.steps["flaky"].outputs["attempt"] == 3


def test_retry_exhaustion_and_on_error_continue(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {
                "id": "failing",
                "use": "test.flaky",
                "with": {"key": "exhaust", "succeed_on_attempt": 5},
                "retry": 2,
                "on_error": "continue",
            },
            {"id": "after", "use": "core.echo", "with": {"value": "still runs"}},
        ),
        tmp_path,
    )
    assert result.status is RunStatus.FAILED
    assert result.steps["failing"].status is StepStatus.FAILED
    assert result.steps["failing"].attempts == 2
    assert result.steps["after"].status is StepStatus.SUCCESS


def test_fail_fast_cancels_pending_steps(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {"id": "fail", "use": "core.fail", "with": {"message": "boom"}},
            {"id": "never", "use": "core.sleep", "with": {"seconds": 1}},
        ),
        tmp_path,
    )
    assert result.status is RunStatus.FAILED
    assert result.steps["fail"].status is StepStatus.FAILED
    assert result.steps["never"].status is StepStatus.CANCELLED


def test_timeout(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {
                "id": "slow",
                "use": "core.sleep",
                "with": {"seconds": 0.5},
                "timeout_s": 0.05,
            }
        ),
        tmp_path,
    )
    assert result.status is RunStatus.FAILED
    assert "timed out" in (result.steps["slow"].error or "")


def test_async_node(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(engine, flow({"id": "async", "use": "test.async_echo", "with": {"value": 7}}), tmp_path)
    assert result.status is RunStatus.SUCCESS
    assert result.steps["async"].outputs["value"] == 7


def test_flow_outputs_and_output_aliases(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {
                "id": "echo",
                "use": "core.echo",
                "with": {"value": 5},
                "outputs": {"renamed": "value"},
            },
            outputs={"renamed": "${steps.echo.renamed}"},
        ),
        tmp_path,
    )
    assert result.outputs == {"renamed": 5}


def test_subflow(tmp_path: Path) -> None:
    child = tmp_path / "child.yaml"
    child.write_text(
        """
version: "2.0"
name: child
inputs:
  name: world
steps:
  - id: greet
    use: core.echo
    with:
      value: "hello ${inputs.name}"
outputs:
  greeting: "${steps.greet.value}"
""",
        encoding="utf-8",
    )
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {
                "id": "child",
                "use": "flow.call",
                "with": {"flow": str(child), "inputs": {"name": "nexus"}},
            },
            outputs={"greeting": "${steps.child.child.outputs.greeting}"},
        ),
        tmp_path,
    )
    assert result.status is RunStatus.SUCCESS
    assert result.outputs == {"greeting": "hello nexus"}


def test_dry_run_does_not_execute(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(engine, flow({"id": "record", "use": "test.record", "with": {"value": 1}}), tmp_path, dry_run=True)
    assert result.status is RunStatus.SUCCESS
    assert result.steps["record"].status is StepStatus.SKIPPED
    assert result.metadata["dry_run"] is True


def test_context_paths_and_variables(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow(
            {"id": "context", "use": "test.context"},
            vars={"a": 1},
            config={"nested": {"x": "y"}},
        ),
        tmp_path,
        variables={"b": 2},
    )
    outputs = result.steps["context"].outputs
    assert outputs["workdir"] == str(tmp_path)
    assert outputs["vars"] == {"a": 1, "b": 2}
    assert outputs["config"] == {"nested": {"x": "y"}}


def test_input_validation_failure(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    result = run(
        engine,
        flow({"id": "bad", "use": "test.flaky", "with": {"unknown": 1}}),
        tmp_path,
    )
    assert result.status is RunStatus.FAILED
    assert "invalid inputs" in (result.steps["bad"].error or "")


def test_event_listener(tmp_path: Path) -> None:
    events: list[str] = []
    settings = EngineSettings(
        project_root=tmp_path,
        node_modules=[],
        load_entry_points=False,
    )
    engine = Engine(settings=settings, event_listener=lambda event: events.append(event.type))
    result = run(engine, flow({"id": "a", "use": "core.noop"}), tmp_path)
    assert result.status is RunStatus.SUCCESS
    assert "run_started" in events
    assert "step_started" in events
    assert "step_finished" in events
    assert "run_finished" in events


def test_implicit_dependency_is_enforced_at_runtime(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, strategy="dag", max_workers=2)
    result = run(
        engine,
        flow(
            {"id": "a", "use": "core.echo", "with": {"value": 2}},
            {"id": "b", "use": "core.echo", "with": {"value": "${steps.a.value * 3}"}},
            outputs={"value": "${steps.b.value}"},
        ),
        tmp_path,
    )
    assert result.status is RunStatus.SUCCESS
    assert result.outputs == {"value": 6}


def test_no_fail_fast_keeps_scheduling(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, fail_fast=False)
    result = run(
        engine,
        flow(
            {"id": "fail", "use": "core.fail", "with": {"message": "boom"}},
            {"id": "after", "use": "core.echo", "with": {"value": "ok"}},
        ),
        tmp_path,
    )
    assert result.status is RunStatus.FAILED
    assert result.steps["after"].status is StepStatus.SUCCESS


def test_execution_precedence(tmp_path: Path) -> None:
    settings = EngineSettings(
        project_root=tmp_path,
        node_modules=[],
        load_entry_points=False,
        execution={"strategy": "dag", "max_workers": 3},
    )
    engine = Engine(settings=settings)

    # Engine defaults apply when the flow does not specify execution.
    defaults = run(engine, flow({"id": "a", "use": "core.noop"}), tmp_path)
    assert defaults.metadata["strategy"] == "dag"
    assert defaults.metadata["max_workers"] == 3

    # Explicit flow fields override engine defaults.
    explicit = run(
        engine,
        flow({"id": "a", "use": "core.noop"}, execution={"strategy": "sequential"}),
        tmp_path,
    )
    assert explicit.metadata["strategy"] == "sequential"

    # Run overrides win over both.
    overridden = engine.run(
        load_flow_dict(flow({"id": "a", "use": "core.noop"}), source="test.yaml"),
        workdir=tmp_path,
        execution={"strategy": "dag", "max_workers": 2},
    )
    assert overridden.metadata["strategy"] == "dag"
    assert overridden.metadata["max_workers"] == 2
