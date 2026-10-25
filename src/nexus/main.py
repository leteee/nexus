"""Programmatic convenience API for Nexus 2.0.

The CLI is a thin wrapper around :class:`nexus.Engine`; applications can use the
helpers below or instantiate the engine directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .core.config import EngineSettings, load_settings
from .core.engine import Engine
from .core.models import FlowSpec, RunResult


def create_engine(
    project_root: Path | str | None = None,
    *,
    settings: EngineSettings | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Engine:
    """Create an engine for a project."""

    if settings is None:
        settings = load_settings(project_root, overrides=overrides)
    return Engine(settings=settings)


def run_flow(
    flow: FlowSpec | str | Path,
    *,
    workdir: Path | str | None = None,
    variables: Mapping[str, Any] | None = None,
    inputs: Mapping[str, Any] | None = None,
    project_root: Path | str | None = None,
    settings: EngineSettings | None = None,
) -> RunResult:
    """Run a flow with a fresh engine."""

    engine = create_engine(project_root, settings=settings)
    return engine.run(flow, workdir=workdir, variables=variables, inputs=inputs)


def validate_flow(
    flow: FlowSpec | str | Path,
    *,
    project_root: Path | str | None = None,
    settings: EngineSettings | None = None,
) -> list[str]:
    """Return validation errors for a flow (empty means valid)."""

    engine = create_engine(project_root, settings=settings)
    return engine.validate(flow)
