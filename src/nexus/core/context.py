"""
Context definitions for the Nexus framework.

Following data_replay's immutable context pattern with dataclasses.
Provides clean separation of concerns and thread-safe execution.
"""

from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

from .datahub import DataHub


@dataclass(frozen=True)
class NexusContext:
    """
    Immutable global context for pipeline execution.

    Contains all the information needed for a complete pipeline run,
    following data_replay's context pattern.
    """
    project_root: Path
    case_path: Path
    logger: Logger
    run_config: Dict[str, Any] = field(default_factory=dict)

    def create_datahub(self) -> DataHub:
        """Create a DataHub instance for this context."""
        return DataHub(case_path=self.case_path, logger=self.logger)


@dataclass(frozen=True)
class PluginContext:
    """
    Immutable context provided to plugins during execution.

    Contains everything a plugin needs to execute, including
    data access, logging, and configuration.
    """
    datahub: DataHub
    logger: Logger
    project_root: Path
    case_path: Path
    config: Optional[BaseModel] = None
    output_path: Optional[Path] = None

    @classmethod
    def from_nexus_context(
        cls,
        nexus_context: NexusContext,
        datahub: DataHub,
        config: Optional[BaseModel] = None,
        output_path: Optional[Path] = None
    ) -> "PluginContext":
        """Create a PluginContext from a NexusContext."""
        return cls(
            datahub=datahub,
            logger=nexus_context.logger,
            project_root=nexus_context.project_root,
            case_path=nexus_context.case_path,
            config=config,
            output_path=output_path
        )