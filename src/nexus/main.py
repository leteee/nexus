"""
Main entry point for Nexus framework.

Provides direct access to core components and convenience functions
for programmatic usage.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import logging

from .core.engine import PipelineEngine
from .core.discovery import plugin, get_plugin, list_plugins
from .cli import main as cli_main


def create_engine(
    project_root: Optional[Path] = None,
    case_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> PipelineEngine:
    """
    Create a PipelineEngine instance.

    Args:
        project_root: Path to project root (auto-detected if None)
        case_path: Path to case directory (defaults to cases/default)
        logger: Custom logger instance

    Returns:
        Configured PipelineEngine instance
    """
    if project_root is None:
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                project_root = current
                break
            current = current.parent
        else:
            raise ValueError("Could not find project root (looking for pyproject.toml)")

    if case_path is None:
        case_path = project_root / "cases" / "default"

    return PipelineEngine(
        project_root=project_root,
        case_path=case_path,
        logger_instance=logger
    )


def run_pipeline(
    case_path: Optional[Path] = None,
    pipeline_config: Optional[Path] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None
) -> None:
    """
    Execute a pipeline programmatically.

    Args:
        case_path: Path to case directory
        pipeline_config: Path to pipeline configuration file
        config_overrides: Configuration overrides
        project_root: Path to project root (auto-detected if None)
    """
    engine = create_engine(project_root, case_path)
    engine.run_pipeline(pipeline_config, config_overrides)


def run_plugin(
    plugin_name: str,
    config_overrides: Optional[Dict[str, Any]] = None,
    case_path: Optional[Path] = None,
    project_root: Optional[Path] = None
) -> Any:
    """
    Execute a single plugin programmatically.

    Args:
        plugin_name: Name of the plugin to execute
        config_overrides: Configuration overrides
        case_path: Path to case directory
        project_root: Path to project root (auto-detected if None)

    Returns:
        Plugin execution result
    """
    engine = create_engine(project_root, case_path)
    return engine.run_plugin(plugin_name, config_overrides)


# Re-export core components for convenience
__all__ = [
    "create_engine",
    "run_pipeline",
    "run_plugin",
    "plugin",
    "get_plugin",
    "list_plugins",
    "cli_main",
]