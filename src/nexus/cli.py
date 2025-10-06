"""
Simplified CLI for Nexus framework.

Clear, focused commands with simple logic:
- nexus run --case <case> [--template <template>] [--config key=value]
- nexus plugin <plugin_name> --case <case> [--config key=value]
- nexus list [templates|cases|plugins]
- nexus help [--plugin <plugin>]
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click

from .core.case_manager import CaseManager
from .core.config import load_yaml
from .core.discovery import get_plugin, list_plugins
from .core.engine import PipelineEngine


def find_project_root(start_path: Path) -> Path:
    """Find project root by looking for pyproject.toml."""
    current = start_path
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return start_path


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_config_overrides(config_list: tuple) -> Dict[str, Any]:
    """Parse --config key=value pairs into nested dictionary."""
    config = {}
    for item in config_list:
        if "=" not in item:
            click.echo(f"Invalid config format: {item}. Use key=value format.")
            continue

        key, value = item.split("=", 1)

        # Handle nested keys like plugins.DataGenerator.num_rows
        keys = key.split(".")
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Try to parse value as int/float/bool, fall back to string
        try:
            if value.lower() in ("true", "false"):
                current[keys[-1]] = value.lower() == "true"
            elif value.isdigit():
                current[keys[-1]] = int(value)
            elif "." in value and value.replace(".", "").isdigit():
                current[keys[-1]] = float(value)
            else:
                current[keys[-1]] = value
        except (ValueError, AttributeError):
            current[keys[-1]] = value

    return config


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version information")
@click.pass_context
def cli(ctx, version):
    """Nexus - A modern data processing framework."""
    if version:
        click.echo("Nexus 0.2.0")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option(
    "--case",
    "-c",
    required=True,
    help="Case directory (relative to cases_root or absolute path)",
)
@click.option("--template", "-t", help="Template name to use (copy-on-first-use)")
@click.option(
    "--config", "-C", multiple=True, help="Config overrides (key=value format)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def run(case: str, template: Optional[str], config: tuple, verbose: bool):
    """
    Run a pipeline in the specified case using case.yaml configuration.

    Template Behavior:
    - With template: Copy template to case.yaml if missing, otherwise reference template
    - Without template: Use existing case.yaml (must exist)

    Examples:
      nexus run --case my-analysis                          # Use case.yaml
      nexus run --case my-analysis --template etl-pipeline  # Copy/reference template
      nexus run --case /abs/path --config plugins.DataGenerator.num_rows=5000
    """
    setup_logging("DEBUG" if verbose else "INFO")

    try:
        # Find project root and load global config
        project_root = find_project_root(Path.cwd())
        global_config = load_yaml(project_root / "config" / "global.yaml")
        cases_root = global_config.get("framework", {}).get("cases_root", "cases")

        # Initialize case manager and get pipeline config
        case_manager = CaseManager(project_root, cases_root)
        config_path, pipeline_config = case_manager.get_pipeline_config(case, template)

        # Parse config overrides
        config_overrides = parse_config_overrides(config)

        # Get case directory for data path resolution
        case_dir = case_manager.resolve_case_path(case)

        # Create and run pipeline
        engine = PipelineEngine(project_root, case_dir)
        engine.run_pipeline(pipeline_config, config_overrides)

        click.echo(f"✓ Pipeline completed successfully in case: {case}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("plugin_name")
@click.option("--case", "-c", required=True, help="Case directory for data context")
@click.option(
    "--config", "-C", multiple=True, help="Config overrides (key=value format)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def plugin(plugin_name: str, case: str, config: tuple, verbose: bool):
    """
    Run a single plugin in the specified case with automatic data discovery.

    This command intelligently handles case configuration:
    - If case.yaml exists: Uses defined data sources + auto-discovered files
    - If no case.yaml: Automatically discovers CSV, JSON, Parquet, Excel, XML files
    - Creates case directory if it doesn't exist

    Examples:
      nexus plugin "Data Generator" --case my-analysis --config num_rows=1000
      nexus plugin "Data Validator" --case /path/to/data  # Auto-discovers files
    """
    setup_logging("DEBUG" if verbose else "INFO")

    try:
        # Find project root and setup case context
        project_root = find_project_root(Path.cwd())
        global_config = load_yaml(project_root / "config" / "global.yaml")
        cases_root = global_config.get("framework", {}).get("cases_root", "cases")

        case_manager = CaseManager(project_root, cases_root)
        case_dir = case_manager.resolve_case_path(case)
        case_dir.mkdir(parents=True, exist_ok=True)

        # Parse config overrides
        config_overrides = parse_config_overrides(config)

        # Create engine and run single plugin
        engine = PipelineEngine(project_root, case_dir)
        result = engine.run_single_plugin(plugin_name, config_overrides)

        click.echo(f"✓ Plugin '{plugin_name}' completed successfully")
        click.echo(f"Result type: {type(result).__name__}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument(
    "what", type=click.Choice(["templates", "cases", "plugins"]), default="plugins"
)
def list(what: str):
    """
    List available templates, cases, or plugins.

    Arguments:
      templates  Show available pipeline templates
      cases      Show existing cases with case.yaml files
      plugins    Show available plugins (default)

    Examples:
      nexus list                # List plugins (default)
      nexus list templates      # List available templates
      nexus list cases          # List existing cases
    """
    try:
        project_root = find_project_root(Path.cwd())

        if what == "templates":
            global_config = load_yaml(project_root / "config" / "global.yaml")
            cases_root = global_config.get("framework", {}).get("cases_root", "cases")
            case_manager = CaseManager(project_root, cases_root)

            templates = case_manager.list_available_templates()
            if templates:
                click.echo("Available templates:")
                for template in sorted(templates):
                    click.echo(f"  {template}")
            else:
                click.echo("No templates found in templates/ directory")

        elif what == "cases":
            global_config = load_yaml(project_root / "config" / "global.yaml")
            cases_root = global_config.get("framework", {}).get("cases_root", "cases")
            case_manager = CaseManager(project_root, cases_root)

            cases = case_manager.list_existing_cases()
            if cases:
                click.echo("Existing cases:")
                for case in sorted(cases):
                    click.echo(f"  {case}")
            else:
                click.echo(f"No cases found in {cases_root}/ directory")

        elif what == "plugins":
            plugins = list_plugins()
            if plugins:
                click.echo("Available plugins:")
                for plugin_name in sorted(plugins.keys()):
                    plugin_spec = plugins[plugin_name]
                    click.echo(f"  {plugin_name}")
                    if plugin_spec.description:
                        click.echo(f"    {plugin_spec.description}")
            else:
                click.echo("No plugins found")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--plugin", help="Show help for specific plugin")
def help(plugin: Optional[str]):
    """Show detailed help information."""
    if plugin:
        try:
            plugin_spec = get_plugin(plugin)
            click.echo(f"Plugin: {plugin}")
            if plugin_spec.description:
                click.echo(f"Description: {plugin_spec.description}")

            # Show configuration options if available
            if plugin_spec.config_model:
                click.echo("Configuration options:")
                # This would show field info from pydantic model
                for (
                    field_name,
                    field_info,
                ) in plugin_spec.config_model.model_fields.items():
                    default_val = (
                        field_info.default
                        if field_info.default is not None
                        else "Required"
                    )
                    click.echo(f"  {field_name}: {default_val}")

        except Exception as e:
            click.echo(f"✗ Plugin '{plugin}' not found: {e}", err=True)
            sys.exit(1)
    else:
        click.echo(
            """
Nexus - A modern data processing framework

Basic Usage:
  nexus run --case my-analysis                    # Run case with case.yaml
  nexus run --case my-analysis --template etl     # Copy/reference template
  nexus plugin "Data Generator" --case my-analysis # Run single plugin

Commands:
  run      Run a pipeline in specified case
  plugin   Run a single plugin (with auto data discovery)
  list     List available templates/cases/plugins
  help     Show this help or plugin-specific help

Key Features:
  - Auto Data Discovery: Automatically finds CSV, JSON, Parquet files
  - Smart Configuration: CLI > Case > Template > Global hierarchy
  - Template System: Copy-on-first-use, reference thereafter
  - Case Isolation: Each case has its own data and config context

Examples:
  # Pipeline execution
  nexus run --case financial-analysis --template etl-pipeline
  nexus run --case /path/to/analysis --config plugins.DataGenerator.num_rows=5000

  # Single plugin with auto-discovery (no case.yaml needed)
  nexus plugin "Data Validator" --case new-project
  nexus plugin "Data Cleaner" --case financial-analysis --config outlier_threshold=3.0

  # Discovery and help
  nexus list templates
  nexus list cases
  nexus help --plugin "Data Generator"

Path Support:
  --case relative-path      # Relative to cases_root in config
  --case /absolute/path     # Absolute path to case directory
  --case my-project/sub     # Nested case organization

Auto Data Discovery:
  When no case.yaml exists, automatically discovers:
  - CSV files -> csv handler
  - JSON files -> json handler
  - Parquet files -> parquet handler
  - Excel files -> excel handler
  - XML files -> xml handler
        """
        )


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
