"""Flow graph construction, validation and planning."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .errors import FlowValidationError
from .expr import extract_step_refs
from .models import FlowSpec, ForeachSpec, StepSpec


@dataclass
class FlowGraph:
    """Validated dependency graph for a flow."""

    flow: FlowSpec
    steps: dict[str, StepSpec]
    dependencies: dict[str, set[str]]
    dependents: dict[str, set[str]]
    order: list[str] = field(default_factory=list)
    levels: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow": self.flow.name,
            "strategy": self.flow.execution.strategy,
            "steps": [
                {
                    "id": step_id,
                    "use": self.steps[step_id].use,
                    "depends_on": sorted(self.dependencies[step_id]),
                }
                for step_id in self.order
            ],
            "levels": self.levels,
        }

    def to_mermaid(self) -> str:
        lines = ["flowchart TD"]
        for step_id in self.order:
            step = self.steps[step_id]
            label = step.name or step_id
            lines.append(f'    {step_id}["{label}<br/><small>{step.use}</small>"]')
        for step_id in self.order:
            for dependency in sorted(self.dependencies[step_id]):
                lines.append(f"    {dependency} --> {step_id}")
        return "\n".join(lines)


def _iter_expression_refs(step: StepSpec) -> set[str]:
    refs: set[str] = set()
    refs |= extract_step_refs(step.when, bare=True)
    if isinstance(step.foreach, ForeachSpec):
        refs |= extract_step_refs(step.foreach.items, bare=True)
    elif step.foreach is not None:
        refs |= extract_step_refs(step.foreach, bare=True)
    refs |= extract_step_refs(step.inputs, bare=False)
    return refs


def _visit_cycle(
    node: str,
    dependencies: dict[str, set[str]],
    path: list[str],
    seen: set[str],
) -> list[str] | None:
    if node in path:
        index = path.index(node)
        return path[index:] + [node]
    if node in seen:
        return None
    path.append(node)
    seen.add(node)
    for dependency in dependencies.get(node, ()):
        cycle = _visit_cycle(dependency, dependencies, path, seen)
        if cycle:
            return cycle
    path.pop()
    return None


def _find_cycle(nodes: Iterable[str], dependencies: dict[str, set[str]]) -> list[str]:
    """Return one cycle path, or an empty list when the graph is acyclic."""

    for start in list(nodes):
        cycle = _visit_cycle(start, dependencies, [], set())
        if cycle:
            return cycle
    return []


def build_graph(flow: FlowSpec) -> FlowGraph:
    """Build and validate the dependency graph of *flow*.

    Dependencies come from explicit ``needs`` plus any ``steps.<id>`` reference
    found in expressions.  In ``sequential`` mode, declaration order is also
    enforced with implicit edges, which makes the common case predictable while
    still allowing ``dag`` mode for maximum parallelism.
    """

    errors: list[str] = []
    steps = flow.step_map
    dependencies: dict[str, set[str]] = {step.id: set(step.needs) for step in flow.steps}

    for index, step in enumerate(flow.steps):
        for dependency in step.needs:
            if dependency not in steps:
                errors.append(f"step '{step.id}' needs unknown step '{dependency}'")
            if dependency == step.id:
                errors.append(f"step '{step.id}' cannot depend on itself")

        referenced = _iter_expression_refs(step)
        for dependency in sorted(referenced):
            if dependency not in steps:
                errors.append(f"step '{step.id}' references unknown step '{dependency}' in an expression")
            elif dependency == step.id:
                errors.append(f"step '{step.id}' cannot reference its own outputs")
            else:
                dependencies[step.id].add(dependency)

        if flow.execution.strategy == "sequential" and index > 0:
            previous = flow.steps[index - 1].id
            if previous != step.id:
                dependencies[step.id].add(previous)

    for output_ref in sorted(extract_step_refs(flow.outputs, bare=False)):
        if output_ref not in steps:
            errors.append(f"flow outputs reference unknown step '{output_ref}'")

    if errors:
        raise FlowValidationError(errors)

    dependents: dict[str, set[str]] = {step.id: set() for step in flow.steps}
    for step_id, deps in dependencies.items():
        for dependency in deps:
            dependents[dependency].add(step_id)

    # Kahn's algorithm with declaration-order tie breaking.
    declaration_index = {step.id: index for index, step in enumerate(flow.steps)}
    indegree = {step_id: len(deps) for step_id, deps in dependencies.items()}
    ready = sorted((step_id for step_id, degree in indegree.items() if degree == 0), key=lambda step_id: declaration_index[step_id])
    order: list[str] = []
    levels: list[list[str]] = []
    level_of: dict[str, int] = {}

    while ready:
        layer = list(ready)
        levels.append(layer)
        next_ready: set[str] = set()
        for step_id in layer:
            order.append(step_id)
            level_of[step_id] = len(levels) - 1
            for dependent in dependents[step_id]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    next_ready.add(dependent)
        ready = sorted(next_ready, key=lambda step_id: declaration_index[step_id])

    if len(order) != len(steps):
        cycle = _find_cycle(set(steps) - set(order), dependencies)
        path = " -> ".join(reversed(cycle)) if cycle else "unknown cycle"
        raise FlowValidationError([f"dependency cycle detected: {path}", "use 'needs' and expressions to form a DAG"])

    # Ensure stable plan levels even when a step has multiple dependencies at
    # different depths (Kahn layers are already correct, but re-sort by index).
    for layer in levels:
        layer.sort(key=lambda step_id: declaration_index[step_id])

    return FlowGraph(
        flow=flow,
        steps=steps,
        dependencies=dependencies,
        dependents=dependents,
        order=order,
        levels=levels,
    )
