"""Shared fixtures and test-only nodes."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from nexus.core.context import NodeContext
from nexus.core.registry import NodeInput, node

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECORDS: list[Any] = []
FAIL_COUNTERS: dict[str, int] = {}
BARRIER = threading.Barrier(2)


class FlakyInput(NodeInput):
    key: str
    succeed_on_attempt: int = 99


@node("test.flaky", inputs=FlakyInput, tags=["test"])
def flaky(ctx: NodeContext, inputs: FlakyInput) -> dict[str, Any]:
    attempt = FAIL_COUNTERS.get(inputs.key, 0) + 1
    FAIL_COUNTERS[inputs.key] = attempt
    if attempt < inputs.succeed_on_attempt:
        raise RuntimeError(f"attempt {attempt} failed")
    return {"attempt": attempt}


class RecordInput(NodeInput):
    value: Any = None


@node("test.record", inputs=RecordInput, tags=["test"])
def record(ctx: NodeContext, inputs: RecordInput) -> dict[str, Any]:
    RECORDS.append(inputs.value)
    return {"value": inputs.value, "count": len(RECORDS)}


class AsyncInput(NodeInput):
    value: Any = None


@node("test.async_echo", inputs=AsyncInput, tags=["test"])
async def async_echo(ctx: NodeContext, inputs: AsyncInput) -> dict[str, Any]:
    return {"value": inputs.value, "run_id": ctx.run_id}


class ContextInput(NodeInput):
    pass


@node("test.context", inputs=ContextInput, tags=["test"])
def context_info(ctx: NodeContext, inputs: ContextInput) -> dict[str, Any]:
    return {
        "run_id": ctx.run_id,
        "flow": ctx.flow_name,
        "step": ctx.step_id,
        "workdir": str(ctx.workdir),
        "vars": dict(ctx.vars),
        "config": dict(ctx.config),
        "steps": sorted(ctx.steps),
        "item": ctx.scope.get("item"),
        "index": ctx.scope.get("index"),
    }


class BarrierInput(NodeInput):
    pass


@node("test.barrier", inputs=BarrierInput, tags=["test"])
def barrier(ctx: NodeContext, inputs: BarrierInput) -> dict[str, Any]:
    BARRIER.wait(timeout=1.0)
    return {"ok": True}


@pytest.fixture(autouse=True)
def reset_test_state() -> None:
    global BARRIER
    RECORDS.clear()
    FAIL_COUNTERS.clear()
    BARRIER = threading.Barrier(2)


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT
