from __future__ import annotations

from pathlib import Path

import pytest

from nexus.core.config import EngineSettings
from nexus.core.engine import Engine
from nexus.core.errors import FlowValidationError
from nexus.core.graph import build_graph
from nexus.core.loader import load_flow_dict


def base_flow(steps: list[dict], **extra: object) -> dict:
    payload = {"version": "2.0", "name": "test", "steps": steps}
    payload.update(extra)
    return payload


def test_load_and_graph_validation() -> None:
    flow = load_flow_dict(
        base_flow(
            [
                {"id": "a", "use": "core.noop"},
                {"id": "b", "use": "core.noop", "needs": ["a"]},
            ]
        )
    )
    graph = build_graph(flow)
    assert graph.order == ["a", "b"]
    assert graph.levels == [["a"], ["b"]]


def test_implicit_dependency_from_expression() -> None:
    flow = load_flow_dict(
        base_flow(
            [
                {"id": "a", "use": "core.echo", "with": {"value": 1}},
                {"id": "b", "use": "core.echo", "with": {"value": "${steps.a.value}"}},
            ],
            execution={"strategy": "dag"},
        )
    )
    graph = build_graph(flow)
    assert graph.dependencies["b"] == {"a"}


def test_sequential_mode_adds_implicit_edges() -> None:
    flow = load_flow_dict(
        base_flow(
            [
                {"id": "a", "use": "core.noop"},
                {"id": "b", "use": "core.noop"},
                {"id": "c", "use": "core.noop"},
            ]
        )
    )
    graph = build_graph(flow)
    assert graph.dependencies["b"] == {"a"}
    assert graph.dependencies["c"] == {"b"}


def test_dag_mode_keeps_roots_independent() -> None:
    flow = load_flow_dict(
        base_flow(
            [
                {"id": "a", "use": "core.noop"},
                {"id": "b", "use": "core.noop"},
            ],
            execution={"strategy": "dag", "max_workers": 2},
        )
    )
    graph = build_graph(flow)
    assert graph.dependencies["a"] == set()
    assert graph.dependencies["b"] == set()
    assert graph.levels == [["a", "b"]]


def test_duplicate_step_ids() -> None:
    with pytest.raises(FlowValidationError):
        load_flow_dict(
            base_flow(
                [
                    {"id": "a", "use": "core.noop"},
                    {"id": "a", "use": "core.noop"},
                ]
            )
        )


def test_unknown_dependency() -> None:
    with pytest.raises(FlowValidationError):
        load_flow_dict(base_flow([{"id": "a", "use": "core.noop", "needs": ["missing"]}]))


def test_unknown_step_reference() -> None:
    with pytest.raises(FlowValidationError):
        load_flow_dict(
            base_flow(
                [
                    {"id": "a", "use": "core.echo", "with": {"value": "${steps.missing.x}"}},
                ]
            )
        )


def test_cycle_detection() -> None:
    with pytest.raises(FlowValidationError, match="cycle"):
        load_flow_dict(
            base_flow(
                [
                    {"id": "a", "use": "core.noop", "needs": ["b"]},
                    {"id": "b", "use": "core.noop", "needs": ["a"]},
                ],
                execution={"strategy": "dag"},
            )
        )


def test_invalid_version() -> None:
    with pytest.raises(FlowValidationError):
        load_flow_dict({"version": "1.0", "steps": [{"id": "a", "use": "core.noop"}]})


def test_unknown_node_is_reported(tmp_path: Path) -> None:
    settings = EngineSettings(project_root=tmp_path, node_modules=[], load_entry_points=False)
    engine = Engine(settings=settings)
    flow = load_flow_dict(base_flow([{"id": "a", "use": "does.not.exist"}]))
    errors = engine.validate(flow)
    assert errors and "not registered" in errors[0]
