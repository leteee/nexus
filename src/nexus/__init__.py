"""Nexus 2.0 public API."""

from __future__ import annotations

from .core.config import EngineSettings, load_settings
from .core.context import NodeContext
from .core.engine import Engine
from .core.errors import (
    ConfigError,
    ExecutionError,
    ExpressionError,
    FlowError,
    FlowValidationError,
    NexusError,
    NodeLoadError,
    NodeNotFoundError,
    StepExecutionError,
    SubflowError,
)
from .core.expr import ExpressionResolver, evaluate_expression, resolve_value
from .core.graph import FlowGraph
from .core.loader import load_flow_dict, load_flow_file, load_flow_text
from .core.models import (
    ExecutionSettings,
    FlowSpec,
    ForeachSpec,
    RetryPolicy,
    RunEvent,
    RunResult,
    RunStatus,
    StepResult,
    StepSpec,
    StepStatus,
)
from .core.registry import NodeInput, NodeRegistry, NodeSpec, node
from .core.utils import jsonable

__version__ = "2.0.0"

__all__ = [
    "Engine",
    "EngineSettings",
    "load_settings",
    "NodeContext",
    "NodeInput",
    "NodeRegistry",
    "NodeSpec",
    "node",
    "FlowSpec",
    "FlowGraph",
    "ExecutionSettings",
    "ForeachSpec",
    "RetryPolicy",
    "StepSpec",
    "StepResult",
    "StepStatus",
    "RunResult",
    "RunEvent",
    "RunStatus",
    "load_flow_dict",
    "load_flow_file",
    "load_flow_text",
    "ExpressionResolver",
    "evaluate_expression",
    "resolve_value",
    "jsonable",
    "NexusError",
    "ConfigError",
    "FlowError",
    "FlowValidationError",
    "NodeNotFoundError",
    "NodeLoadError",
    "StepExecutionError",
    "SubflowError",
    "ExecutionError",
    "ExpressionError",
    "__version__",
]
