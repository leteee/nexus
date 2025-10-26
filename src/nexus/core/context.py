"""
Context definitions for the Nexus framework.

Provides lightweight immutable contexts used during pipeline execution.
"""

from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel


@dataclass(frozen=True)
class NexusContext:
    """Global execution context shared across plugins."""

    project_root: Path
    case_path: Path
    logger: Logger
    run_config: Dict[str, Any] = field(default_factory=dict)

    def create_plugin_context(
        self,
        *,
        config: Optional[BaseModel] = None,
        shared_state: Dict[str, Any],
    ) -> "PluginContext":
        """Produce a PluginContext for a plugin invocation."""
        return PluginContext(
            project_root=self.project_root,
            case_path=self.case_path,
            logger=self.logger,
            config=config,
            shared_state=shared_state,
        )


@dataclass
class PluginContext:
    """Context passed to plugins during execution."""

    project_root: Path
    case_path: Path
    logger: Logger
    config: Optional[BaseModel] = None
    shared_state: Dict[str, Any] = field(default_factory=dict)

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve a path relative to the case directory."""
        path = Path(value)
        if path.is_absolute():
            return path
        return self.case_path / path

    def remember(self, key: str, value: Any) -> None:
        """Store a value in the shared state for subsequent plugins."""
        self.shared_state[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        """Retrieve a value stored by a previous plugin."""
        return self.shared_state.get(key, default)
