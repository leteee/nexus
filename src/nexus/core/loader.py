"""Flow loading and validation."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .errors import FlowError, FlowValidationError, NodeNotFoundError
from .graph import FlowGraph, build_graph
from .models import FlowSpec
from .registry import NodeRegistry


def load_flow_file(path: Path | str) -> FlowSpec:
    """Load a flow from a YAML file and validate its structure."""

    flow_path = Path(path)
    try:
        text = flow_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FlowError(f"cannot read flow file {flow_path}: {exc}") from exc
    return load_flow_text(text, source=str(flow_path))


def load_flow_text(text: str, *, source: str = "<string>") -> FlowSpec:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise FlowError(f"invalid YAML in {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise FlowError(f"flow {source} must contain a mapping at the top level")
    return load_flow_dict(data, source=source)


def load_flow_dict(data: dict[str, Any], *, source: str = "<dict>") -> FlowSpec:
    payload = dict(data)
    if not payload.get("name"):
        if source.endswith((".yaml", ".yml")):
            payload["name"] = Path(source).stem
        else:
            payload["name"] = "flow"
    try:
        flow = FlowSpec.model_validate(payload)
    except ValidationError as exc:
        errors: list[str] = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ()))
            errors.append(f"{location or 'flow'}: {error.get('msg', 'invalid value')}")
        raise FlowValidationError(errors) from exc
    build_graph(flow)
    return flow


def validate_flow(flow: FlowSpec, registry: NodeRegistry, *, raise_on_error: bool = True) -> list[str]:
    """Check node references and build the graph.

    Returns a list of human-readable errors.  When *raise_on_error* is true a
    :class:`FlowValidationError` is raised instead.
    """

    errors: list[str] = []
    for step in flow.steps:
        try:
            registry.get(step.use)
        except NodeNotFoundError as exc:
            errors.append(f"step '{step.id}': {exc}")

    try:
        build_graph(flow)
    except FlowValidationError as exc:
        errors.extend(exc.errors)

    if errors and raise_on_error:
        raise FlowValidationError(errors)
    return errors


def prepare_flow(path: Path | str, registry: NodeRegistry, *, validate_nodes: bool = True) -> tuple[FlowSpec, FlowGraph]:
    flow = load_flow_file(path)
    if validate_nodes:
        validate_flow(flow, registry, raise_on_error=True)
    graph = build_graph(flow)
    return flow, graph


def validate_flow_file(path: Path | str, registry: NodeRegistry) -> tuple[FlowSpec, FlowGraph]:
    return prepare_flow(path, registry, validate_nodes=True)


def available_flows(roots: Iterable[Path]) -> list[str]:
    names: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.y*ml")):
            try:
                names.append(str(path.relative_to(root).with_suffix("")))
            except ValueError:
                names.append(path.stem)
    return sorted(dict.fromkeys(names))
