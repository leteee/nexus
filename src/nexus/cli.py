"""
Command-line interface for Nexus.

Provides CLI commands for running pipelines, executing plugins,
and managing the data processing workflow.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from .core.engine import PipelineEngine
from .core.discovery import list_plugins


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger("nexus")


def find_project_root(start_path: Path) -> Optional[Path]:
    """Find project root by looking for pyproject.toml."""
    current = start_path.resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return None


def parse_config_overrides(override_args: list[str]) -> Dict[str, Any]:
    """Parse configuration overrides from CLI arguments."""
    overrides = {}
    for arg in override_args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        # Try to parse as JSON, fall back to string
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value

        # Support nested keys like plugins.generator.num_rows=500
        keys = key.split(".")
        current = overrides
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = parsed_value

    return overrides


def run_pipeline_command(args) -> int:
    """Execute a pipeline."""
    try:
        project_root = find_project_root(Path.cwd())
        if not project_root:
            print("Error: Could not find project root (looking for pyproject.toml)")
            return 1

        case_path = Path(args.case) if args.case else project_root / "cases" / "default"
        if not case_path.exists():
            print(f"Error: Case path does not exist: {case_path}")
            return 1

        logger = setup_logging(args.log_level)

        # Parse configuration overrides
        config_overrides = parse_config_overrides(args.config or [])

        # Create and run pipeline
        engine = PipelineEngine(
            project_root=project_root,
            case_path=case_path,
            logger_instance=logger
        )

        pipeline_config = Path(args.pipeline) if args.pipeline else None
        engine.run_pipeline(pipeline_config, config_overrides)

        print("Pipeline completed successfully")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


def run_plugin_command(args) -> int:
    """Execute a single plugin."""
    try:
        project_root = find_project_root(Path.cwd())
        if not project_root:
            print("Error: Could not find project root (looking for pyproject.toml)")
            return 1

        case_path = Path(args.case) if args.case else project_root / "cases" / "default"

        logger = setup_logging(args.log_level)

        # Parse configuration overrides
        config_overrides = parse_config_overrides(args.config or [])

        # Create engine and run plugin
        engine = PipelineEngine(
            project_root=project_root,
            case_path=case_path,
            logger_instance=logger
        )

        result = engine.run_plugin(args.plugin, config_overrides)

        if result is not None:
            print(f"Plugin result: {result}")

        print(f"Plugin '{args.plugin}' completed successfully")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


def list_plugins_command(args) -> int:
    """List available plugins."""
    try:
        project_root = find_project_root(Path.cwd())
        if not project_root:
            print("Error: Could not find project root (looking for pyproject.toml)")
            return 1

        case_path = Path(args.case) if args.case else project_root / "cases" / "default"

        logger = setup_logging("ERROR")  # Suppress logs for clean output

        # Initialize engine to trigger plugin discovery
        engine = PipelineEngine(
            project_root=project_root,
            case_path=case_path,
            logger_instance=logger
        )

        plugins = list_plugins()

        if not plugins:
            print("No plugins found")
            return 0

        print(f"Available plugins ({len(plugins)}):")
        print()

        for plugin_spec in plugins.values():
            print(f"  {plugin_spec.name}")
            if plugin_spec.description:
                print(f"    {plugin_spec.description}")
            if plugin_spec.config_model:
                print(f"    Config: {plugin_spec.config_model.__name__}")
            print()

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Nexus - Modern data processing framework",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Pipeline command
    pipeline_parser = subparsers.add_parser(
        "run",
        help="Execute a pipeline"
    )
    pipeline_parser.add_argument(
        "--case", "-c",
        help="Path to case directory (default: cases/default)"
    )
    pipeline_parser.add_argument(
        "--pipeline", "-p",
        help="Path to pipeline configuration file (default: case/case.yaml)"
    )
    pipeline_parser.add_argument(
        "--config",
        nargs="*",
        help="Configuration overrides (key=value format, supports nested keys)"
    )
    pipeline_parser.set_defaults(func=run_pipeline_command)

    # Plugin command
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Execute a single plugin"
    )
    plugin_parser.add_argument(
        "plugin",
        help="Name of the plugin to execute"
    )
    plugin_parser.add_argument(
        "--case", "-c",
        help="Path to case directory (default: cases/default)"
    )
    plugin_parser.add_argument(
        "--config",
        nargs="*",
        help="Configuration overrides (key=value format)"
    )
    plugin_parser.set_defaults(func=run_plugin_command)

    # List plugins command
    list_parser = subparsers.add_parser(
        "list",
        help="List available plugins"
    )
    list_parser.add_argument(
        "--case", "-c",
        help="Path to case directory (default: cases/default)"
    )
    list_parser.set_defaults(func=list_plugins_command)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())