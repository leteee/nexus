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


def load_template_config(global_config: Dict[str, Any]) -> tuple[list[str], bool]:
    """
    Load template discovery configuration from global config.

    Args:
        global_config: Global configuration dictionary

    Returns:
        tuple: (template_paths, template_recursive)
    """
    discovery_config = global_config.get("framework", {}).get("discovery", {})
    template_config = discovery_config.get("templates", {})
    template_paths = template_config.get("paths", ["templates"])
    template_recursive = template_config.get("recursive", False)

    return template_paths, template_recursive


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

        # Load template discovery configuration
        template_paths, template_recursive = load_template_config(global_config)

        # Initialize case manager with template configuration
        case_manager = CaseManager(
            project_root,
            cases_root,
            template_paths=template_paths,
            template_recursive=template_recursive,
        )
        config_path, pipeline_config = case_manager.get_pipeline_config(case, template)

        # Parse config overrides
        config_overrides = parse_config_overrides(config)

        # Get case directory for data path resolution
        case_dir = case_manager.resolve_case_path(case)

        # Create and run pipeline
        engine = PipelineEngine(project_root, case_dir)
        engine.run_pipeline(pipeline_config, config_overrides)

        click.echo(f"SUCCESS: Pipeline completed successfully in case: {case}")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
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

        # Load template discovery configuration
        template_paths, template_recursive = load_template_config(global_config)

        # Initialize case manager with template configuration
        case_manager = CaseManager(
            project_root,
            cases_root,
            template_paths=template_paths,
            template_recursive=template_recursive,
        )
        case_dir = case_manager.resolve_case_path(case)
        case_dir.mkdir(parents=True, exist_ok=True)

        # Parse config overrides
        config_overrides = parse_config_overrides(config)

        # Create engine and run single plugin
        engine = PipelineEngine(project_root, case_dir)
        result = engine.run_single_plugin(plugin_name, config_overrides)

        click.echo(f"SUCCESS: Plugin '{plugin_name}' completed successfully")
        click.echo(f"Result type: {type(result).__name__}")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument(
    "what", type=click.Choice(["templates", "cases", "plugins", "handlers"]), default="plugins"
)
def list(what: str):
    """
    List available templates, cases, plugins, or handlers.

    Arguments:
      templates  Show available pipeline templates
      cases      Show existing cases with case.yaml files
      plugins    Show available plugins (default)
      handlers   Show available data format handlers

    Examples:
      nexus list                # List plugins (default)
      nexus list templates      # List available templates
      nexus list cases          # List existing cases
      nexus list handlers       # List available handlers
    """
    try:
        project_root = find_project_root(Path.cwd())

        if what == "templates":
            global_config = load_yaml(project_root / "config" / "global.yaml")
            cases_root = global_config.get("framework", {}).get("cases_root", "cases")

            # Load template discovery configuration
            template_paths, template_recursive = load_template_config(global_config)

            # Initialize case manager with template configuration
            case_manager = CaseManager(
                project_root,
                cases_root,
                template_paths=template_paths,
                template_recursive=template_recursive,
            )

            templates = case_manager.list_available_templates()
            if templates:
                click.echo("Available templates:")

                # Group by directory if recursive
                if template_recursive:
                    # Show with directory structure
                    current_dir = None
                    for template in sorted(templates):
                        template_dir = str(Path(template).parent) if "/" in template else ""
                        if template_dir != current_dir:
                            if template_dir:
                                click.echo(f"\n  {template_dir}/")
                            current_dir = template_dir

                        template_name = Path(template).name
                        prefix = "    " if template_dir else "  "
                        click.echo(f"{prefix}{template_name}")
                else:
                    # Simple flat list
                    for template in sorted(templates):
                        click.echo(f"  {template}")
            else:
                click.echo("No templates found in search paths")
                click.echo(f"Search paths: {template_paths}")

        elif what == "cases":
            global_config = load_yaml(project_root / "config" / "global.yaml")
            cases_root = global_config.get("framework", {}).get("cases_root", "cases")

            # Load template configuration for consistency
            template_paths, template_recursive = load_template_config(global_config)

            # Initialize case manager
            case_manager = CaseManager(
                project_root,
                cases_root,
                template_paths=template_paths,
                template_recursive=template_recursive,
            )

            cases = case_manager.list_existing_cases()
            if cases:
                click.echo("Existing cases:")
                for case in sorted(cases):
                    click.echo(f"  {case}")
            else:
                click.echo(f"No cases found in {cases_root}/ directory")

        elif what == "plugins":
            ensure_plugins_discovered(project_root)
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

        elif what == "handlers":
            ensure_plugins_discovered(project_root)
            from .core.handlers import HANDLER_REGISTRY

            if HANDLER_REGISTRY:
                click.echo("Available handlers:")
                for handler_name in sorted(HANDLER_REGISTRY.keys()):
                    handler_class = HANDLER_REGISTRY[handler_name]
                    click.echo(f"  {handler_name}")
                    if hasattr(handler_class, "__doc__") and handler_class.__doc__:
                        first_line = handler_class.__doc__.strip().split("\n")[0]
                        click.echo(f"    {first_line}")
            else:
                click.echo("No handlers found")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


def ensure_plugins_discovered(project_root: Path) -> None:
    """
    Ensure plugins and handlers are discovered before generating docs.

    This function triggers plugin and handler discovery if not already done.
    """
    from .core.discovery import (
        discover_plugins_from_module,
        discover_plugins_from_directory,
        discover_plugins_from_paths,
        discover_handlers_from_paths,
        PLUGIN_REGISTRY
    )

    # Skip if already discovered
    if len(PLUGIN_REGISTRY) > 0:
        return

    # Discover built-in plugins
    discover_plugins_from_module("nexus.plugins.generators")
    discover_plugins_from_module("nexus.plugins.processors")

    # Discover from project directories
    plugins_dir = project_root / "src" / "nexus" / "plugins"
    if plugins_dir.exists():
        discover_plugins_from_directory(plugins_dir)

    # Discover from global config
    try:
        global_config = load_yaml(project_root / "config" / "global.yaml")
        discovery_config = global_config.get("framework", {}).get("discovery", {})

        # Plugin discovery
        plugin_config = discovery_config.get("plugins", {})
        plugin_modules = plugin_config.get("modules", [])
        plugin_paths = plugin_config.get("paths", [])

        for module_name in plugin_modules:
            discover_plugins_from_module(module_name)

        if plugin_paths:
            discover_plugins_from_paths([project_root / p for p in plugin_paths])

        # Handler discovery
        handler_config = discovery_config.get("handlers", {})
        handler_paths = handler_config.get("paths", [])

        handlers_dir = project_root / "src" / "nexus" / "core"
        handler_scan_paths = [handlers_dir]
        if handler_paths:
            handler_scan_paths.extend([project_root / p for p in handler_paths])

        discover_handlers_from_paths(handler_scan_paths, project_root)
    except Exception as e:
        # If config loading fails, just use built-in discoveries
        pass


@cli.command()
@click.option("--output", type=click.Path(), default="docs/api", help="Output directory (default: docs/api)")
@click.option("--format", type=click.Choice(["markdown", "rst", "json"]), default="markdown", help="Output format")
@click.option("--force", "-f", is_flag=True, help="Force overwrite without confirmation")
def doc(output: str, format: str, force: bool):
    """
    Generate API documentation for all plugins and handlers.

    This command automatically scans and documents all available plugins and handlers,
    creating structured API documentation in the specified output directory.

    Default Output Structure:
        docs/api/
        ├── plugins/
        │   ├── data_generator.md
        │   ├── sample_data_generator.md
        │   └── README.md          # Plugin index
        ├── handlers/
        │   ├── csv.md
        │   ├── json.md
        │   └── README.md          # Handler index
        └── README.md              # API documentation index

    Examples:
        # Generate all documentation (with confirmation)
        nexus doc

        # Force overwrite without confirmation
        nexus doc --force

        # Custom output directory
        nexus doc --output docs/reference

        # Different format
        nexus doc --format rst
    """
    from pathlib import Path
    from .core.handlers import HANDLER_REGISTRY

    try:
        project_root = find_project_root(Path.cwd())
        output_path = Path(output)

        # Ensure plugins and handlers are discovered
        ensure_plugins_discovered(project_root)

        # Get all plugins and handlers
        all_plugins = list_plugins()
        all_handlers = HANDLER_REGISTRY.copy()

        # Calculate files that will be created/overwritten
        files_to_create = []

        # Plugin files
        plugins_dir = output_path / "plugins"
        for plugin_name in all_plugins.keys():
            safe_name = plugin_name.replace(" ", "_").replace("/", "_").lower()
            ext = "md" if format == "markdown" else "rst" if format == "rst" else "json"
            file_path = plugins_dir / f"{safe_name}.{ext}"
            files_to_create.append(file_path)
        files_to_create.append(plugins_dir / "README.md")

        # Handler files
        handlers_dir = output_path / "handlers"
        for handler_name in all_handlers.keys():
            ext = "md" if format == "markdown" else "rst" if format == "rst" else "json"
            file_path = handlers_dir / f"{handler_name}.{ext}"
            files_to_create.append(file_path)
        files_to_create.append(handlers_dir / "README.md")

        # Main index
        files_to_create.append(output_path / "README.md")

        # Check for existing files
        existing_files = [f for f in files_to_create if f.exists()]

        # Confirm overwrite if needed
        if existing_files and not force:
            click.echo(f"WARNING: {len(existing_files)} files will be overwritten:")
            for f in existing_files[:5]:  # Show first 5
                click.echo(f"   {f}")
            if len(existing_files) > 5:
                click.echo(f"   ... and {len(existing_files) - 5} more")

            if not click.confirm("\nContinue?", default=False):
                click.echo("Cancelled.")
                return

        # Generate plugin documentation
        click.echo(f"Generating documentation for {len(all_plugins)} plugins...")
        _generate_all_plugin_docs(all_plugins, output_path / "plugins", format)

        # Generate handler documentation
        click.echo(f"Generating documentation for {len(all_handlers)} handlers...")
        _generate_all_handler_docs(all_handlers, output_path / "handlers", format)

        # Generate index
        _generate_api_index(output_path, all_plugins, all_handlers)

        click.echo(f"\nSUCCESS: API documentation generated in {output_path}/")
        click.echo(f"  Plugins: {len(all_plugins)}")
        click.echo(f"  Handlers: {len(all_handlers)}")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _generate_all_plugin_docs(plugins: dict, output_dir: Path, format: str) -> None:
    """Generate documentation for all plugins."""
    output_dir.mkdir(parents=True, exist_ok=True)

    plugin_list = []
    for plugin_name, plugin_spec in sorted(plugins.items()):
        safe_name = plugin_name.replace(" ", "_").replace("/", "_").lower()
        ext = "md" if format == "markdown" else "rst" if format == "rst" else "json"
        file_path = output_dir / f"{safe_name}.{ext}"

        # Generate doc content
        if format == "markdown":
            doc_content = _generate_markdown_doc(plugin_name, plugin_spec)
        elif format == "rst":
            doc_content = _generate_rst_doc(plugin_name, plugin_spec)
        else:
            doc_content = _generate_json_doc(plugin_name, plugin_spec)

        # Write file
        file_path.write_text(doc_content, encoding="utf-8")
        plugin_list.append((plugin_name, safe_name, plugin_spec.description or ""))

    # Generate plugin index
    _generate_plugin_index(output_dir, plugin_list, format)


def _generate_all_handler_docs(handlers: dict, output_dir: Path, format: str) -> None:
    """Generate documentation for all handlers."""
    output_dir.mkdir(parents=True, exist_ok=True)

    handler_list = []
    for handler_name, handler_class in sorted(handlers.items()):
        ext = "md" if format == "markdown" else "rst" if format == "rst" else "json"
        file_path = output_dir / f"{handler_name}.{ext}"

        # Generate doc content
        if format == "markdown":
            doc_content = _generate_handler_markdown_doc(handler_name, handler_class)
        elif format == "rst":
            doc_content = _generate_handler_rst_doc(handler_name, handler_class)
        else:
            doc_content = _generate_handler_json_doc(handler_name, handler_class)

        # Write file
        file_path.write_text(doc_content, encoding="utf-8")
        handler_list.append((handler_name, handler_class))

    # Generate handler index
    _generate_handler_index(output_dir, handler_list, format)


def _generate_plugin_index(output_dir: Path, plugin_list: list, format: str) -> None:
    """Generate index file for plugins."""
    if format != "markdown":
        return

    lines = []
    lines.append("# Plugins API Reference")
    lines.append("")
    lines.append("This directory contains auto-generated documentation for all available plugins.")
    lines.append("")
    lines.append(f"**Total Plugins**: {len(plugin_list)}")
    lines.append("")
    lines.append("## Available Plugins")
    lines.append("")

    for plugin_name, safe_name, description in sorted(plugin_list):
        lines.append(f"### [{plugin_name}]({safe_name}.md)")
        if description:
            lines.append(f"{description}")
        lines.append("")

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _generate_handler_index(output_dir: Path, handler_list: list, format: str) -> None:
    """Generate index file for handlers."""
    if format != "markdown":
        return

    lines = []
    lines.append("# Handlers API Reference")
    lines.append("")
    lines.append("This directory contains auto-generated documentation for all available data handlers.")
    lines.append("")
    lines.append(f"**Total Handlers**: {len(handler_list)}")
    lines.append("")
    lines.append("## Available Handlers")
    lines.append("")

    for handler_name, handler_class in sorted(handler_list):
        lines.append(f"### [{handler_name.upper()}]({handler_name}.md)")
        if hasattr(handler_class, "__doc__") and handler_class.__doc__:
            lines.append(f"{handler_class.__doc__.strip().split(chr(10))[0]}")
        lines.append("")

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _generate_api_index(output_dir: Path, plugins: dict, handlers: dict) -> None:
    """Generate main API index."""
    lines = []
    lines.append("# Nexus API Reference")
    lines.append("")
    lines.append("Auto-generated API documentation for Nexus framework.")
    lines.append("")
    lines.append("## Contents")
    lines.append("")

    if plugins:
        lines.append(f"- **[Plugins](plugins/README.md)** - {len(plugins)} available plugins")
    if handlers:
        lines.append(f"- **[Handlers](handlers/README.md)** - {len(handlers)} data format handlers")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*This documentation is automatically generated by `nexus doc` command.*")
    lines.append("")

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _generate_handler_markdown_doc(handler_name: str, handler_class) -> str:
    """Generate markdown documentation for a handler."""
    lines = []
    lines.append(f"# {handler_name.upper()} Handler")
    lines.append("")

    # Description
    if hasattr(handler_class, "__doc__") and handler_class.__doc__:
        lines.append("## Overview")
        lines.append("")
        lines.append(handler_class.__doc__.strip())
        lines.append("")

    # Produced type
    try:
        handler_instance = handler_class()
        produced_type = handler_instance.produced_type
        lines.append("## Produced Type")
        lines.append("")
        lines.append(f"**Type**: `{produced_type.__name__ if hasattr(produced_type, '__name__') else str(produced_type)}`")
        lines.append("")
    except Exception:
        pass

    # Methods
    lines.append("## Methods")
    lines.append("")
    lines.append("### `load(path: Path) -> Any`")
    lines.append("Load data from the specified file path.")
    lines.append("")
    lines.append("### `save(data: Any, path: Path) -> None`")
    lines.append("Save data to the specified file path.")
    lines.append("")

    # Usage example
    lines.append("## Usage Example")
    lines.append("")
    lines.append("### In Plugin Configuration")
    lines.append("```python")
    lines.append("from typing import Annotated")
    lines.append("from nexus import PluginConfig, DataSource, DataSink")
    lines.append("")
    lines.append("class MyConfig(PluginConfig):")
    lines.append(f'    input_data: Annotated[str, DataSource(handler="{handler_name}")] = "data/input.{handler_name}"')
    lines.append(f'    output_data: Annotated[str, DataSink(handler="{handler_name}")] = "data/output.{handler_name}"')
    lines.append("```")
    lines.append("")

    lines.append("### In YAML Configuration")
    lines.append("```yaml")
    lines.append("pipeline:")
    lines.append('  - plugin: "My Plugin"')
    lines.append("    config:")
    lines.append(f'      input_data: "data/input.{handler_name}"')
    lines.append(f'      output_data: "data/output.{handler_name}"')
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def _generate_handler_rst_doc(handler_name: str, handler_class) -> str:
    """Generate RST documentation for a handler."""
    lines = []
    title = f"{handler_name.upper()} Handler"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    if hasattr(handler_class, "__doc__") and handler_class.__doc__:
        lines.append(handler_class.__doc__.strip())
        lines.append("")

    return "\n".join(lines)


def _generate_handler_json_doc(handler_name: str, handler_class) -> str:
    """Generate JSON documentation for a handler."""
    import json as json_module

    doc_data = {
        "name": handler_name,
        "type": "handler",
        "description": handler_class.__doc__.strip() if hasattr(handler_class, "__doc__") and handler_class.__doc__ else "",
        "methods": {
            "load": "Load data from file",
            "save": "Save data to file"
        }
    }

    try:
        handler_instance = handler_class()
        produced_type = handler_instance.produced_type
        doc_data["produced_type"] = produced_type.__name__ if hasattr(produced_type, '__name__') else str(produced_type)
    except Exception:
        pass

    return json_module.dumps(doc_data, indent=2)


def _has_nested_models(config_model) -> bool:
    """Check if config model has nested Pydantic models."""
    from pydantic import BaseModel

    for field_name, field_info in config_model.model_fields.items():
        if _is_nested_model(field_info):
            return True
    return False


def _is_nested_model(field_info) -> bool:
    """Check if a field is a nested Pydantic model."""
    from pydantic import BaseModel
    import inspect

    # Get the actual type, unwrapping Annotated if necessary
    annotation = field_info.annotation
    if hasattr(annotation, "__origin__"):  # Handle generic types
        return False

    # Check if it's a BaseModel subclass
    try:
        return inspect.isclass(annotation) and issubclass(annotation, BaseModel)
    except (TypeError, AttributeError):
        return False


def _get_field_type_name(field_info) -> str:
    """Get a clean type name for a field."""
    annotation = field_info.annotation

    if hasattr(annotation, "__name__"):
        return annotation.__name__
    else:
        # Handle complex types
        type_str = str(annotation)
        # Clean up common patterns
        type_str = type_str.replace("typing.", "")
        return type_str


def _format_default_value(default_val) -> str:
    """Format default value for display in table."""
    if default_val is None:
        return "*(required)*"

    type_name = type(default_val).__name__

    if type_name == 'str':
        return f'`"{default_val}"`'
    elif type_name == 'bool':
        return f'`{str(default_val).lower()}`'
    elif type_name in ('int', 'float'):
        return f'`{default_val}`'
    elif type_name in ('list', 'tuple'):
        return f'`{default_val}`'
    else:
        return f'`{default_val}`'


def _generate_yaml_config(config_model, lines: list, indent: int = 6):
    """Generate YAML configuration with rich comments including type and description."""
    from pydantic import BaseModel

    indent_str = " " * indent

    for field_name, field_info in config_model.model_fields.items():
        # Get default value
        default_val = field_info.default if field_info.default is not None else None

        # Check if it's a nested model
        if _is_nested_model(field_info):
            # Handle nested model
            nested_comment_parts = []
            if field_info.description:
                nested_comment_parts.append(field_info.description)

            comment = f"  # {', '.join(nested_comment_parts)}" if nested_comment_parts else ""
            lines.append(f"{indent_str}{field_name}:{comment}")

            # Get the nested model class
            nested_model = field_info.annotation

            # Generate nested fields
            for nested_field_name, nested_field_info in nested_model.model_fields.items():
                nested_default = nested_field_info.default if nested_field_info.default is not None else None
                formatted_val = _format_yaml_value(nested_default)

                # Build rich comment: type + description
                nested_comment_parts = []
                nested_type = _get_field_type_name(nested_field_info)
                nested_comment_parts.append(nested_type)
                if nested_field_info.description:
                    nested_comment_parts.append(nested_field_info.description)

                nested_comment = f"  # {': '.join(nested_comment_parts)}" if nested_comment_parts else ""
                lines.append(f"{indent_str}  {nested_field_name}: {formatted_val}{nested_comment}")
        else:
            # Simple field
            formatted_val = _format_yaml_value(default_val)

            # Build rich comment: type + description
            comment_parts = []
            field_type = _get_field_type_name(field_info)
            comment_parts.append(field_type)
            if field_info.description:
                comment_parts.append(field_info.description)

            comment = f"  # {': '.join(comment_parts)}" if comment_parts else ""
            lines.append(f"{indent_str}{field_name}: {formatted_val}{comment}")


def _format_yaml_value(value) -> str:
    """Format a value for YAML output."""
    if value is None:
        return "# REQUIRED"

    type_name = type(value).__name__

    if type_name == 'str':
        return f'"{value}"'
    elif type_name == 'bool':
        return str(value).lower()
    elif type_name in ('int', 'float'):
        return str(value)
    elif type_name in ('list', 'tuple'):
        if not value:  # Empty list
            return "[]"
        return str(value)
    elif type_name == 'PydanticUndefinedType':
        return "# REQUIRED"
    else:
        # For complex types, try to serialize
        try:
            return str(value)
        except:
            return "# REQUIRED"


def _generate_markdown_doc(plugin_name: str, plugin_spec) -> str:
    """Generate markdown documentation for a plugin."""
    from pydantic import BaseModel

    lines = []
    lines.append(f"# {plugin_name}")
    lines.append("")

    # Overview (function docstring only)
    if plugin_spec.func.__doc__:
        lines.append("## Overview")
        lines.append("")
        lines.append(plugin_spec.func.__doc__.strip())
        lines.append("")

    # Configuration (YAML only - no redundant table)
    if plugin_spec.config_model:
        lines.append("## Configuration")
        lines.append("")
        lines.append("```yaml")
        lines.append("pipeline:")
        lines.append(f'  - plugin: "{plugin_name}"')
        lines.append("    config:")

        # Generate YAML with rich comments (type + description)
        _generate_yaml_config(plugin_spec.config_model, lines, indent=6)

        lines.append("```")
        lines.append("")

    # CLI Usage
    lines.append("## CLI Usage")
    lines.append("")
    lines.append("```bash")
    lines.append(f'# Run with defaults')
    lines.append(f'nexus plugin "{plugin_name}" --case mycase')
    lines.append("")
    if plugin_spec.config_model:
        # Show example with meaningful field names (exclude nested models from CLI examples)
        field_items = [item for item in plugin_spec.config_model.model_fields.items()
                      if not _is_nested_model(item[1])][:2]
        if field_items:
            lines.append(f'# Run with custom config')
            lines.append(f'nexus plugin "{plugin_name}" --case mycase \\')
            for i, (field_name, _) in enumerate(field_items):
                connector = " \\" if i < len(field_items) - 1 else ""
                lines.append(f'  -C {field_name}=value{connector}')
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
