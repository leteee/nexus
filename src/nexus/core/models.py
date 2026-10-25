"""Pydantic models describing flows, steps and run results.

The models in this module are the public contract of the engine.  They are
intentionally strict (``extra="forbid"``) so that typos in a flow file fail at
validation time instead of being silently ignored at runtime.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STEP_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NODE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class NexusModel(BaseModel):
    """Base model used across Nexus public schemas."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RetryPolicy(NexusModel):
    """Retry policy for a step or a single ``foreach`` iteration."""

    max_attempts: int = Field(default=1, ge=1, description="Total attempts, including the first one.")
    delay_s: float = Field(default=0.0, ge=0.0, description="Initial delay between attempts in seconds.")
    backoff: float = Field(default=1.0, ge=0.0, description="Multiplier applied to the delay after each failure.")
    max_delay_s: float = Field(default=30.0, ge=0.0, description="Upper bound for the delay in seconds.")
    jitter_s: float = Field(default=0.0, ge=0.0, description="Maximum random jitter added to each delay.")

    @classmethod
    def coerce(cls, value: Any) -> RetryPolicy | None:
        if value is None or isinstance(value, RetryPolicy):
            return value
        if isinstance(value, bool):
            raise TypeError("retry must be a mapping or an integer")
        if isinstance(value, int):
            return cls(max_attempts=value)
        if isinstance(value, dict):
            return cls.model_validate(value)
        raise TypeError(f"Unsupported retry value: {value!r}")


class ForeachSpec(NexusModel):
    """Describes how a step is expanded over a collection."""

    items: Any = Field(description="Expression or literal list to iterate over.")
    item_name: str = Field(default="item", alias="as", description="Name bound to the current item.")
    index_name: str = Field(default="index", alias="index", description="Name bound to the current index.")
    concurrency: int = Field(default=1, ge=1, description="Number of iterations to run in parallel.")

    @field_validator("item_name", "index_name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value.isidentifier():
            raise ValueError(f"'{value}' is not a valid Python identifier")
        return value


class ExecutionSettings(NexusModel):
    """How the scheduler executes a flow's steps."""

    strategy: Literal["sequential", "dag"] = Field(
        default="sequential",
        description="'sequential' keeps declaration order; 'dag' runs every ready step concurrently.",
    )
    max_workers: int = Field(default=1, ge=1, le=256, description="Maximum number of concurrently running steps.")
    fail_fast: bool = Field(default=True, description="Stop scheduling new steps after the first failure.")
    step_timeout_s: float | None = Field(
        default=None,
        gt=0,
        description="Default timeout applied to every step without its own timeout.",
    )


class StepSpec(NexusModel):
    """One executable unit in a flow."""

    id: str = Field(description="Unique step identifier used by expressions and dependencies.")
    use: str = Field(description="Registered node type, for example 'core.python'.")
    name: str | None = Field(default=None, description="Human readable step name.")
    description: str | None = None
    needs: list[str] = Field(default_factory=list, description="Explicit step dependencies.")
    inputs: dict[str, Any] = Field(default_factory=dict, alias="with", description="Node inputs.")
    when: bool | str | None = Field(default=None, description="Condition controlling whether the step runs.")
    foreach: ForeachSpec | list[Any] | str | None = Field(default=None, description="Expand the step over items.")
    outputs: dict[str, str] | list[str] | None = Field(
        default=None,
        description="Select or rename node outputs. A mapping exposes {'alias': 'node_result_key'}.",
    )
    retry: RetryPolicy | int | None = Field(default=None, description="Retry policy or a simple max-attempt count.")
    timeout_s: float | None = Field(default=None, gt=0, description="Per-attempt timeout in seconds.")
    on_error: Literal["fail", "continue"] = Field(default="fail", description="Failure behaviour.")
    tags: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not STEP_ID_PATTERN.match(value):
            raise ValueError(
                f"invalid step id '{value}'; use letters, digits and underscores, starting with a letter or underscore"
            )
        return value

    @field_validator("use")
    @classmethod
    def _validate_use(cls, value: str) -> str:
        if not NODE_NAME_PATTERN.match(value):
            raise ValueError(f"invalid node name '{value}'")
        return value

    @field_validator("needs", mode="before")
    @classmethod
    def _coerce_needs(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("retry", mode="before")
    @classmethod
    def _coerce_retry(cls, value: Any) -> Any:
        return RetryPolicy.coerce(value)

    @field_validator("outputs", mode="before")
    @classmethod
    def _coerce_outputs(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise ValueError("outputs list entries must be strings")
            return value
        if isinstance(value, dict):
            if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
                raise ValueError("outputs mapping must map alias -> node output key (both strings)")
            return value
        raise ValueError("outputs must be a list of keys or a mapping alias -> key")

    @property
    def retry_policy(self) -> RetryPolicy:
        if isinstance(self.retry, RetryPolicy):
            return self.retry
        if isinstance(self.retry, int):
            return RetryPolicy(max_attempts=self.retry)
        return RetryPolicy()

    @property
    def is_foreach(self) -> bool:
        return self.foreach is not None


class FlowSpec(NexusModel):
    """A complete declarative flow."""

    version: str = Field(default="2.0", description="Flow schema version; must be 2.x.")
    name: str | None = Field(default=None, description="Flow name; defaults to the file stem.")
    description: str | None = None
    vars: dict[str, Any] = Field(default_factory=dict, description="Flow-scoped variables.")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Default inputs for subflow invocation.")
    config: dict[str, Any] = Field(default_factory=dict, description="Application configuration exposed as `config`.")
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    steps: list[StepSpec] = Field(description="Ordered step declarations.")
    outputs: dict[str, Any] = Field(default_factory=dict, description="Flow outputs exposed to callers.")

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        text = str(value)
        if text != "2" and not text.startswith("2."):
            raise ValueError(f"unsupported flow version '{value}'; Nexus 2.x expects version '2.0' or newer 2.x")
        return text

    @model_validator(mode="after")
    def _validate_steps(self) -> FlowSpec:
        if not self.steps:
            raise ValueError("flow must contain at least one step")
        seen: set[str] = set()
        duplicates: list[str] = []
        for step in self.steps:
            if step.id in seen:
                duplicates.append(step.id)
            seen.add(step.id)
        if duplicates:
            raise ValueError(f"duplicate step ids: {', '.join(sorted(set(duplicates)))}")

        known = {step.id for step in self.steps}
        unknown: list[str] = []
        for step in self.steps:
            for dependency in step.needs:
                if dependency not in known:
                    unknown.append(f"step '{step.id}' needs unknown step '{dependency}'")
                if dependency == step.id:
                    unknown.append(f"step '{step.id}' cannot depend on itself")
        if unknown:
            raise ValueError("; ".join(unknown))
        return self

    @property
    def step_map(self) -> dict[str, StepSpec]:
        return {step.id: step for step in self.steps}


class StepStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepResult(NexusModel):
    """Outcome of one step (or one foreach aggregate)."""

    id: str
    use: str
    status: StepStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_traceback: str | None = None
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status is StepStatus.SUCCESS


class RunResult(NexusModel):
    """Outcome of a complete flow run."""

    run_id: str
    flow: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    steps: dict[str, StepResult] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.SUCCESS


class RunEvent(NexusModel):
    """Structured runtime event, useful for logging and observability."""

    type: str
    timestamp: datetime
    run_id: str
    flow: str
    step: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
