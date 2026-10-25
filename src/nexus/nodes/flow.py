"""Built-in composition nodes."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from nexus.core.context import NodeContext
from nexus.core.errors import SubflowError
from nexus.core.registry import NodeInput, node


class FlowCallInput(NodeInput):
    flow: str = Field(description="Flow path or name, resolved like the CLI resolves flows.")
    workdir: str | None = Field(default=None, description="Child working directory; defaults to the parent workdir.")
    vars: dict[str, Any] = Field(default_factory=dict, description="Variables passed to the child flow.")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Explicit inputs for the child flow.")
    inherit_vars: bool = Field(default=False, description="Merge the parent flow's variables into the child.")
    allow_failure: bool = Field(default=False, description="Return a failed result instead of raising.")


@node(
    "flow.call",
    inputs=FlowCallInput,
    tags=["flow", "composition"],
    description="Execute another flow as a child run and expose its outputs.",
)
def call_flow(ctx: NodeContext, inputs: FlowCallInput) -> dict[str, Any]:
    result = ctx.run_flow(
        inputs.flow,
        workdir=inputs.workdir,
        variables=inputs.vars,
        inputs=inputs.inputs,
        inherit_vars=inputs.inherit_vars,
    )
    if not result.ok and not inputs.allow_failure:
        raise SubflowError(f"subflow '{inputs.flow}' failed: {result.error}")

    return {
        "child": {
            "status": result.status.value,
            "run_id": result.run_id,
            "outputs": result.outputs,
            "steps": {step_id: step.status.value for step_id, step in result.steps.items()},
            "error": result.error,
            "duration_ms": result.duration_ms,
        }
    }
