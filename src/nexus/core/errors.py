"""Exception hierarchy for the Nexus execution engine."""

from __future__ import annotations

from collections.abc import Iterable


class NexusError(Exception):
    """Base class for all Nexus errors."""


class ConfigError(NexusError):
    """Invalid engine or flow configuration."""


class FlowError(NexusError):
    """A flow definition is invalid."""


class FlowValidationError(FlowError):
    """A flow failed structural validation."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        message = "Invalid flow:\n" + "\n".join(f"  - {error}" for error in self.errors)
        super().__init__(message)


class NodeNotFoundError(FlowError):
    """A referenced node type is not registered."""


class ExpressionError(NexusError):
    """An expression or template reference could not be evaluated."""


class ExecutionError(NexusError):
    """Base class for runtime execution failures."""


class StepExecutionError(ExecutionError):
    """A single step failed after exhausting retries."""

    def __init__(self, step_id: str, message: str, *, cause: BaseException | None = None) -> None:
        self.step_id = step_id
        self.cause = cause
        super().__init__(f"Step '{step_id}' failed: {message}")


class RunCancelledError(ExecutionError):
    """A run was cancelled because fail-fast was triggered."""


class SubflowError(ExecutionError):
    """A subflow could not be executed."""


class NodeLoadError(NexusError):
    """A node pack could not be loaded."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message
        super().__init__(f"Failed to load node pack '{source}': {message}")
