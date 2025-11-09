"""
Context definitions for the Nexus framework.

Provides lightweight immutable contexts used during pipeline execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Any, Dict, Optional, Set, Union

from pydantic import BaseModel

from .path_resolver import auto_resolve_paths


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
    """
    Context passed to plugins during execution.

    Provides utilities for path resolution, state management, and logging.
    Automatically resolves path parameters following the '*_path' convention.
    """

    project_root: Path
    case_path: Path
    logger: Logger
    config: Optional[BaseModel] = None
    shared_state: Dict[str, Any] = field(default_factory=dict)

    def resolve_path(self, value: Union[str, Path]) -> Path:
        """
        Resolve a path relative to the case directory.

        Args:
            value: Path string or Path object

        Returns:
            Absolute path

        Example:
            >>> ctx.resolve_path("input/data.json")
            Path("/abs/case/path/input/data.json")
        """
        path = Path(value)
        if path.is_absolute():
            return path
        return self.case_path / path

    def auto_resolve_paths(
        self,
        config: Union[Dict[str, Any], BaseModel],
        skip_keys: Optional[Set[str]] = None,
    ) -> Union[Dict[str, Any], BaseModel]:
        """
        Automatically resolve all parameters ending with '_path'.

        Convention:
            Any parameter named '*_path' will be resolved to an absolute path
            relative to the case directory.

        Args:
            config: Configuration dict or Pydantic model
            skip_keys: Optional set of keys to skip resolution

        Returns:
            Configuration with all *_path parameters resolved

        Example:
            >>> params = {
            ...     "data_path": "input/data.json",
            ...     "output_path": "output/results.csv",
            ...     "threshold": 0.5
            ... }
            >>> resolved = ctx.auto_resolve_paths(params)
            >>> # data_path and output_path are now absolute paths

            >>> # With Pydantic model
            >>> config = MyConfig(data_path="input/data.json")
            >>> ctx.auto_resolve_paths(config)
            >>> # config.data_path is now absolute path
        """
        return auto_resolve_paths(config, self.resolve_path, skip_keys)

    def remember(self, key: str, value: Any) -> None:
        """Store a value in the shared state for subsequent plugins."""
        self.shared_state[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        """Retrieve a value stored by a previous plugin."""
        return self.shared_state.get(key, default)
