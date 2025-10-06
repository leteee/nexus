"""
Simplified main entry point for Nexus framework.

Provides clean programmatic access to the core functionality.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .core.case_manager import CaseManager
from .core.config import load_yaml
from .core.engine import PipelineEngine


def create_engine(
    case_path: str, project_root: Optional[Path] = None
) -> PipelineEngine:
    """
    Create a PipelineEngine instance for a specific case.

    Args:
        case_path: Case identifier or absolute path
        project_root: Path to project root (auto-detected if None)

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
            project_root = Path.cwd()

    # Load global config and resolve case path
    global_config = load_yaml(project_root / "config" / "global.yaml")
    cases_root = global_config.get("framework", {}).get("cases_root", "cases")

    case_manager = CaseManager(project_root, cases_root)
    case_dir = case_manager.resolve_case_path(case_path)

    return PipelineEngine(project_root, case_dir)


def run_pipeline(
    case_path: str,
    template_name: Optional[str] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run a complete pipeline in the specified case.

    Args:
        case_path: Case identifier or absolute path
        template_name: Template to use (optional)
        config_overrides: Configuration overrides
        project_root: Path to project root (auto-detected if None)

    Returns:
        Dictionary of all pipeline outputs
    """
    if project_root is None:
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                project_root = current
                break
            current = current.parent
        else:
            project_root = Path.cwd()

    # Load global config and get pipeline configuration
    global_config = load_yaml(project_root / "config" / "global.yaml")
    cases_root = global_config.get("framework", {}).get("cases_root", "cases")

    case_manager = CaseManager(project_root, cases_root)
    config_path, pipeline_config = case_manager.get_pipeline_config(
        case_path, template_name
    )
    case_dir = case_manager.resolve_case_path(case_path)

    # Create and run pipeline
    engine = PipelineEngine(project_root, case_dir)
    return engine.run_pipeline(pipeline_config, config_overrides)


def run_plugin(
    plugin_name: str,
    case_path: str,
    config_overrides: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
) -> Any:
    """
    Run a single plugin in the specified case.

    Args:
        plugin_name: Name of plugin to execute
        case_path: Case identifier or absolute path
        config_overrides: Configuration overrides
        project_root: Path to project root (auto-detected if None)

    Returns:
        Plugin execution result
    """
    if project_root is None:
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                project_root = current
                break
            current = current.parent
        else:
            project_root = Path.cwd()

    # Load global config and resolve case path
    global_config = load_yaml(project_root / "config" / "global.yaml")
    cases_root = global_config.get("framework", {}).get("cases_root", "cases")

    case_manager = CaseManager(project_root, cases_root)
    case_dir = case_manager.resolve_case_path(case_path)

    # Create and run plugin
    engine = PipelineEngine(project_root, case_dir)
    return engine.run_single_plugin(plugin_name, config_overrides)
