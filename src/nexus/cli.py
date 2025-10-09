"""
Simplified CLI for Nexus framework.

Clear, focused commands with simple logic:
- nexus run --case <case> [--template <template>] [--config key=value]
- nexus plugin <plugin_name> --case <case> [--config key=value]
- nexus list [templates|cases|plugins]
- nexus help [--plugin <plugin>]
"""

import logging
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
    """
    Parse --config key=value pairs into nested dictionary.

    Supports:
    - Nested keys with dot notation: framework.logging.level=DEBUG
    - Automatic type inference: true/false → bool, 123 → int, 0.5 → float
    - JSON values: key='{"a": 1}' or key='[1, 2, 3]'
    - String values: key=value or key="quoted value"

    Valid namespaces:
    - framework.*: Framework settings (logging, performance, discovery)
    - data_sources.*: Global/shared data sources
    - plugins.*: Plugin configuration defaults

    Examples:
        framework.logging.level=DEBUG
        data_sources.my_source.path=data.csv
        plugins.DataGenerator.num_rows=5000
        plugins.MyPlugin.config='{"key": "value"}'
    """
    import json

    config = {}
    valid_namespaces = {"framework", "data_sources", "plugins"}

    for item in config_list:
        if "=" not in item:
            click.echo(f"Invalid config format: {item}. Use key=value format.")
            continue

        key, value = item.split("=", 1)

        # Validate namespace (first part of key)
        keys = key.split(".")
        if len(keys) > 1 and keys[0] not in valid_namespaces:
            click.echo(
                f"Warning: Invalid namespace '{keys[0]}' in {key}. "
                f"Valid namespaces: {', '.join(sorted(valid_namespaces))}"
            )
            # Continue anyway for flexibility, but warn user

        # Navigate to nested location
        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Try to parse value with intelligent type inference
        final_value = value

        # Try JSON parsing first (for objects and arrays)
        if value.startswith('{') or value.startswith('['):
            try:
                final_value = json.loads(value)
            except json.JSONDecodeError:
                # Not valid JSON, treat as string
                pass
        # Boolean
        elif value.lower() in ("true", "false"):
            final_value = value.lower() == "true"
        # Integer
        elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
            final_value = int(value)
        # Float
        elif '.' in value:
            try:
                final_value = float(value)
            except ValueError:
                # Not a valid float, keep as string
                pass
        # Remove quotes if present
        elif value.startswith('"') and value.endswith('"'):
            final_value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            final_value = value[1:-1]

        current[keys[-1]] = final_value

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
@click.option("--template", "-t", help="Template to use (replaces case.yaml)")
@click.option(
    "--config", "-C", multiple=True, help="Config overrides (key=value format)"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def run(case: str, template: Optional[str], config: tuple, verbose: bool):
    """
    Run a pipeline in the specified case.

    Template Behavior:
    - With --template: Use template (case.yaml ignored, template replaces it)
    - Without --template: Use case.yaml (must exist)

    Templates and case.yaml are mutually exclusive, not a config hierarchy.

    Examples:
      nexus run --case my-analysis                          # Use case.yaml
      nexus run --case my-analysis --template etl-pipeline  # Use template
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
@click.option("--plugin", help="Generate docs for specific plugin")
@click.option(
    "--output",
    type=click.Path(),
    help="Output file path (default: stdout or docs/plugins/<name>.md)",
)
@click.option(
    "--format",
    type=click.Choice(["markdown", "rst", "json"]),
    default="markdown",
    help="Output format",
)
@click.option("--all", is_flag=True, help="Generate docs for all plugins")
def doc(plugin: Optional[str], output: Optional[str], format: str, all: bool):
    """Generate documentation for plugins.

    Examples:
        nexus doc --plugin "Data Generator"
        nexus doc --plugin "Data Generator" --output docs/generator.md
        nexus doc --all --output docs/plugins/
        nexus doc --plugin "My Plugin" --format json
    """
    from pathlib import Path

    try:
        plugins_to_document = []

        if all:
            # Get all plugins
            all_plugins = list_plugins()
            plugins_to_document = list(all_plugins.keys())
        elif plugin:
            # Get specific plugin
            plugins_to_document = [plugin]
        else:
            click.echo("Error: Must specify --plugin <name> or --all", err=True)
            sys.exit(1)

        for plugin_name in plugins_to_document:
            try:
                plugin_spec = get_plugin(plugin_name)

                # Generate documentation based on format
                if format == "markdown":
                    doc_content = _generate_markdown_doc(plugin_name, plugin_spec)
                elif format == "rst":
                    doc_content = _generate_rst_doc(plugin_name, plugin_spec)
                elif format == "json":
                    doc_content = _generate_json_doc(plugin_name, plugin_spec)
                else:
                    doc_content = _generate_markdown_doc(plugin_name, plugin_spec)

                # Determine output destination
                if output:
                    output_path = Path(output)
                    if all and output_path.is_dir():
                        # Generate separate file for each plugin
                        safe_name = (
                            plugin_name.replace(" ", "_").replace("/", "_").lower()
                        )
                        ext = (
                            "md"
                            if format == "markdown"
                            else "rst" if format == "rst" else "json"
                        )
                        file_path = output_path / f"{safe_name}.{ext}"
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(doc_content, encoding="utf-8")
                        click.echo(f"✓ Generated documentation: {file_path}")
                    else:
                        # Single output file
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        if all:
                            # Append to file
                            with output_path.open("a", encoding="utf-8") as f:
                                f.write(doc_content)
                                f.write("\n\n---\n\n")
                        else:
                            output_path.write_text(doc_content, encoding="utf-8")
                        click.echo(f"✓ Generated documentation: {output_path}")
                else:
                    # Output to stdout
                    click.echo(doc_content)
                    if all and plugin_name != plugins_to_document[-1]:
                        click.echo("\n\n---\n\n")

            except Exception as e:
                click.echo(f"✗ Error documenting plugin '{plugin_name}': {e}", err=True)
                if not all:
                    sys.exit(1)

        if all:
            click.echo(
                f"\n✓ Generated documentation for {len(plugins_to_document)} plugins"
            )

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


def _generate_markdown_doc(plugin_name: str, plugin_spec) -> str:
    """Generate markdown documentation for a plugin."""
    import inspect

    lines = []
    lines.append(f"# {plugin_name}")
    lines.append("")

    # Description
    if plugin_spec.description:
        lines.append(f"**Description**: {plugin_spec.description}")
        lines.append("")

    # Function docstring
    if plugin_spec.func.__doc__:
        lines.append("## Overview")
        lines.append("")
        lines.append(plugin_spec.func.__doc__.strip())
        lines.append("")

    # Configuration
    if plugin_spec.config_model:
        lines.append("## Configuration")
        lines.append("")
        lines.append("| Parameter | Type | Default | Description |")
        lines.append("|-----------|------|---------|-------------|")

        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            field_type = (
                field_info.annotation.__name__
                if hasattr(field_info.annotation, "__name__")
                else str(field_info.annotation)
            )
            default = (
                field_info.default if field_info.default is not None else "*(required)*"
            )
            description = field_info.description or ""
            lines.append(
                f"| `{field_name}` | `{field_type}` | {default} | {description} |"
            )

        lines.append("")

    # Function signature
    lines.append("## Function Signature")
    lines.append("")
    try:
        sig = inspect.signature(plugin_spec.func)
        lines.append("```python")
        lines.append(f"def {plugin_spec.func.__name__}{sig}:")
        lines.append("    ...")
        lines.append("```")
        lines.append("")
    except Exception:
        pass

    # Data sources (if any)
    if hasattr(plugin_spec.func, "__data_sources__"):
        lines.append("## Data Sources")
        lines.append("")
        for source in plugin_spec.func.__data_sources__:
            lines.append(f"- `{source}`")
        lines.append("")

    # Data sinks (if any)
    if hasattr(plugin_spec.func, "__data_sinks__"):
        lines.append("## Data Sinks")
        lines.append("")
        for sink in plugin_spec.func.__data_sinks__:
            lines.append(f"- `{sink}`")
        lines.append("")

    # Usage example
    lines.append("## Usage Example")
    lines.append("")
    lines.append("### CLI")
    lines.append("```bash")
    lines.append(f'nexus plugin "{plugin_name}" --case mycase')
    if plugin_spec.config_model:
        # Show example config
        first_field = next(iter(plugin_spec.config_model.model_fields.keys()), None)
        if first_field:
            lines.append(
                f'nexus plugin "{plugin_name}" --case mycase --config {first_field}=value'
            )
    lines.append("```")
    lines.append("")

    lines.append("### Python API")
    lines.append("```python")
    lines.append("from nexus import create_engine")
    lines.append("")
    lines.append('engine = create_engine("mycase")')
    lines.append(f'result = engine.run_single_plugin("{plugin_name}")')
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def _generate_rst_doc(plugin_name: str, plugin_spec) -> str:
    """Generate reStructuredText documentation for a plugin."""
    lines = []
    lines.append(plugin_name)
    lines.append("=" * len(plugin_name))
    lines.append("")

    if plugin_spec.description:
        lines.append(plugin_spec.description)
        lines.append("")

    if plugin_spec.func.__doc__:
        lines.append(plugin_spec.func.__doc__.strip())
        lines.append("")

    if plugin_spec.config_model:
        lines.append("Configuration")
        lines.append("-" * 13)
        lines.append("")
        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            field_type = (
                field_info.annotation.__name__
                if hasattr(field_info.annotation, "__name__")
                else str(field_info.annotation)
            )
            default = (
                field_info.default if field_info.default is not None else "*(required)*"
            )
            description = field_info.description or ""
            lines.append(
                f":{field_name}: ({field_type}) {description}. Default: {default}"
            )
        lines.append("")

    return "\n".join(lines)


def _generate_json_doc(plugin_name: str, plugin_spec) -> str:
    """Generate JSON documentation for a plugin."""
    import inspect
    import json as json_module

    doc_data = {
        "name": plugin_name,
        "description": plugin_spec.description or "",
        "docstring": (
            plugin_spec.func.__doc__.strip() if plugin_spec.func.__doc__ else ""
        ),
        "configuration": {},
        "data_sources": getattr(plugin_spec.func, "__data_sources__", []),
        "data_sinks": getattr(plugin_spec.func, "__data_sinks__", []),
    }

    if plugin_spec.config_model:
        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            field_type = (
                field_info.annotation.__name__
                if hasattr(field_info.annotation, "__name__")
                else str(field_info.annotation)
            )
            doc_data["configuration"][field_name] = {
                "type": field_type,
                "default": (
                    str(field_info.default) if field_info.default is not None else None
                ),
                "required": field_info.is_required(),
                "description": field_info.description or "",
            }

    try:
        sig = inspect.signature(plugin_spec.func)
        doc_data["signature"] = str(sig)
    except Exception:
        pass

    return json_module.dumps(doc_data, indent=2)


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
  nexus run --case my-analysis --template etl     # Use template (ignore case.yaml)
  nexus plugin "Data Generator" --case my-analysis # Run single plugin

Commands:
  run      Run a pipeline in specified case
  plugin   Run a single plugin (with auto data discovery)
  list     List available templates/cases/plugins
  help     Show this help or plugin-specific help

Key Features:
  - Auto Data Discovery: Automatically finds CSV, JSON, Parquet files
  - Simple Configuration: CLI > Case/Template > Global > Plugin (4 layers)
  - Template System: Templates replace case.yaml when specified (mutual exclusion)
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
