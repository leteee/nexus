"""
Command line interface for the streamlined Nexus runtime.

The CLI now focuses purely on plugin orchestration without the legacy
DataSource/handler features.
"""

from __future__ import annotations

import builtins
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click

from .core.case_manager import CaseManager
from .core.config import load_global_configuration
from .core.discovery import discover_all_plugins, list_plugins
from .core.engine import PipelineEngine


# ---------------------------------------------------------------------------
# Shared helpers


def find_project_root(start_path: Path) -> Path:
    current = start_path
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return start_path


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _load_case_manager(project_root: Path) -> CaseManager:
    global_config = load_global_configuration(project_root)
    framework_cfg = global_config.get("framework", {})

    cases_roots = framework_cfg.get("cases_roots", ["cases"])
    cases_roots = [cases_roots] if isinstance(cases_roots, str) else builtins.list(cases_roots)

    templates_roots = framework_cfg.get("templates_roots", ["templates"])
    templates_roots = [templates_roots] if isinstance(templates_roots, str) else builtins.list(templates_roots)

    return CaseManager(project_root, cases_roots=cases_roots, templates_roots=templates_roots)


def _discover(project_root: Path) -> None:
    discover_all_plugins(project_root)


def parse_config_overrides(config_list: tuple[str, ...]) -> Dict[str, Any]:
    import json

    config: Dict[str, Any] = {}
    valid_namespaces = {"framework", "plugins"}

    for item in config_list:
        if "=" not in item:
            click.echo(f"Invalid config format: {item}. Use key=value format.")
            continue

        key, value = item.split("=", 1)
        keys = key.split(".")
        if len(keys) > 1 and keys[0] not in valid_namespaces:
            click.echo(
                f"Warning: Invalid namespace '{keys[0]}' in {key}. "
                f"Valid namespaces: {', '.join(sorted(valid_namespaces))}"
            )
            continue

        current = config
        for part in keys[:-1]:
            current = current.setdefault(part, {})

        lower = value.lower()
        if value.startswith("{") or value.startswith("["):
            try:
                current[keys[-1]] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        if lower in {"true", "false"}:
            current[keys[-1]] = lower == "true"
        elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            current[keys[-1]] = int(value)
        else:
            try:
                current[keys[-1]] = float(value)
            except ValueError:
                current[keys[-1]] = value.strip('"')

    return config


# ---------------------------------------------------------------------------
# CLI group


@click.group(invoke_without_command=True, help="Nexus - A modern data processing framework")
@click.option("--version", is_flag=True, help="Show version information")
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    if version:
        from . import __version__

        click.echo(f"Nexus {__version__}")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Commands


@cli.command()
@click.option("--case", "-c", required=True, help="Case directory (relative or absolute)")
@click.option("--template", "-t", help="Template to use (optional)")
@click.option("--config", "-C", multiple=True, help="Config overrides (key=value)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def run(case: str, template: Optional[str], config: tuple[str, ...], verbose: bool) -> None:
    setup_logging("DEBUG" if verbose else "INFO")

    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    try:
        _config_path, case_config = manager.get_case_config(case, template)
    except Exception as exc:  # pylint: disable=broad-except
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    engine = PipelineEngine(project_root, manager.resolve_case_path(case))
    overrides = parse_config_overrides(config)
    try:
        engine.run_pipeline(case_config, overrides)
        click.echo(f"SUCCESS: Pipeline completed for case '{case}'")
    except Exception as exc:  # pylint: disable=broad-except
        click.echo(f"ERROR: {exc}", err=True)
        if verbose:
            raise
        sys.exit(1)


@cli.command(name="plugin")
@click.argument("plugin_name")
@click.option("--case", "-c", required=True, help="Case directory for execution context")
@click.option("--config", "-C", multiple=True, help="Config overrides (key=value)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def plugin_cmd(plugin_name: str, case: str, config: tuple[str, ...], verbose: bool) -> None:
    setup_logging("DEBUG" if verbose else "INFO")

    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)
    engine = PipelineEngine(project_root, manager.resolve_case_path(case))

    overrides = parse_config_overrides(config)
    try:
        result = engine.run_single_plugin(plugin_name, overrides)
    except Exception as exc:  # pylint: disable=broad-except
        click.echo(f"ERROR: {exc}", err=True)
        if verbose:
            raise
        sys.exit(1)

    click.echo(f"SUCCESS: Plugin '{plugin_name}' completed")
    if result is not None:
        click.echo(f"Result type: {type(result).__name__}")


@cli.command(name="list")
@click.argument("what", type=click.Choice(["templates", "cases", "plugins"]), default="plugins")
def list_cmd(what: str) -> None:
    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    if what == "templates":
        templates = manager.list_available_templates()
        if not templates:
            click.echo("No templates found")
            return
        click.echo("Available templates:")
        for tpl in templates:
            click.echo(f"  {tpl}")
    elif what == "cases":
        cases = manager.list_existing_cases()
        if not cases:
            click.echo("No cases found")
            return
        click.echo("Existing cases:")
        for case in cases:
            click.echo(f"  {case}")
    else:
        _discover(project_root)
        plugins = list_plugins()
        if not plugins:
            click.echo("No plugins registered")
            return
        click.echo("Available plugins:")
        for name, spec in sorted(plugins.items()):
            click.echo(f"  {name}")
            if spec.description:
                click.echo(f"    {spec.description}")


@cli.command()
@click.option("--plugin", help="Show help for a specific plugin")
def help(plugin: Optional[str]) -> None:  # pylint: disable=redefined-builtin
    """Show help information for commands or plugins."""
    if not plugin:
        click.echo(cli.get_help(click.Context(cli)))
        return

    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    from .core.discovery import get_plugin
    from pydantic_core import PydanticUndefined

    try:
        spec = get_plugin(plugin)
    except KeyError as exc:
        click.echo(f"ERROR: {exc}")
        sys.exit(1)

    click.echo(f"Plugin: {plugin}")
    click.echo("")
    if spec.description:
        click.echo(spec.description)
        click.echo("")

    if spec.config_model:
        click.echo("Configuration fields:")
        for field_name, field_info in spec.config_model.model_fields.items():
            # Get default value
            default = field_info.default
            if default is PydanticUndefined:
                default_str = "<required>"
            elif default is None:
                default_str = "None"
            else:
                default_str = str(default)

            # Get field type
            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation))

            # Get description
            description = field_info.description or ""

            # Format output
            if description:
                click.echo(f"  - {field_name} ({field_type}): {default_str}")
                click.echo(f"    {description}")
            else:
                click.echo(f"  - {field_name} ({field_type}): {default_str}")


@cli.command(name="doc")
@click.option("--output", type=click.Path(), default="docs/api", help="Output directory (default: docs/api)")
@click.option("--force", "-f", is_flag=True, help="Force overwrite without confirmation")
def doc_cmd(output: str, force: bool) -> None:
    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    plugins = list_plugins()
    if not plugins:
        click.echo("No plugins to document")
        return

    output_path = Path(output)
    plugin_dir = output_path / "plugins"

    if output_path.exists() and not force:
        click.echo("Output directory exists. Use --force to overwrite.")
        sys.exit(1)

    plugin_dir.mkdir(parents=True, exist_ok=True)

    for name, spec in plugins.items():
        safe_name = name.replace(" ", "_").lower()
        file_path = plugin_dir / f"{safe_name}.md"
        file_path.write_text(_generate_plugin_markdown_doc(name, spec), encoding="utf-8")

    (output_path / "README.md").write_text(_generate_plugin_index_markdown(plugins), encoding="utf-8")
    click.echo(f"Documentation written to {output_path}")


# ---------------------------------------------------------------------------
# Documentation helpers


def _generate_yaml_value_from_schema(schema: dict, indent: int = 0) -> list[str]:
    """
    Generate YAML representation from JSON schema recursively.

    Args:
        schema: JSON schema dict from Pydantic
        indent: Current indentation level

    Returns:
        List of YAML lines
    """
    lines = []
    schema_type = schema.get("type")

    # Handle arrays
    if schema_type == "array":
        items_schema = schema.get("items", {})
        items_type = items_schema.get("type")

        if items_type == "object":
            # Array of objects - show example structure
            lines.append("")
            properties = items_schema.get("properties", {})
            if properties:
                # Has defined properties - show full structure
                indent_str = "  " * (indent + 1)
                lines.append(f"{indent_str}- # Example item")
                for prop_name, prop_schema in properties.items():
                    prop_lines = _generate_yaml_value_from_schema(prop_schema, indent + 2)
                    if len(prop_lines) == 1 and not prop_lines[0].startswith("\n"):
                        # Simple value
                        lines.append(f"{indent_str}  {prop_name}: {prop_lines[0]}")
                    else:
                        # Complex value
                        lines.append(f"{indent_str}  {prop_name}:{prop_lines[0]}")
                        lines.extend(prop_lines[1:])
            else:
                # No properties defined - generic dict
                # Show a more useful example with common keys
                indent_str = "  " * (indent + 1)
                lines.append(f"{indent_str}- # Example item (dict)")
                lines.append(f"{indent_str}  key1: \"value1\"")
                lines.append(f"{indent_str}  key2: \"value2\"")
        elif items_type == "string":
            # Array of strings
            lines.append("")
            indent_str = "  " * (indent + 1)
            lines.append(f"{indent_str}- \"item1\"")
            lines.append(f"{indent_str}- \"item2\"")
        elif items_type == "number" or items_type == "integer":
            # Array of numbers
            lines.append("")
            indent_str = "  " * (indent + 1)
            lines.append(f"{indent_str}- 1")
            lines.append(f"{indent_str}- 2")
        else:
            # Array of primitives or unknown
            lines.append(" []")

    # Handle objects
    elif schema_type == "object":
        properties = schema.get("properties", {})
        if properties:
            lines.append("")
            indent_str = "  " * (indent + 1)
            for prop_name, prop_schema in properties.items():
                prop_lines = _generate_yaml_value_from_schema(prop_schema, indent + 1)
                if len(prop_lines) == 1 and not prop_lines[0].startswith("\n"):
                    # Simple value
                    lines.append(f"{indent_str}{prop_name}: {prop_lines[0]}")
                else:
                    # Complex value
                    lines.append(f"{indent_str}{prop_name}:{prop_lines[0]}")
                    lines.extend(prop_lines[1:])
        else:
            lines.append(" {}")

    # Handle primitives
    elif schema_type == "string":
        default = schema.get("default")
        if default:
            lines.append(f'"{default}"')
        else:
            lines.append('"value"')

    elif schema_type == "number" or schema_type == "integer":
        default = schema.get("default")
        if default is not None:
            lines.append(str(default))
        else:
            lines.append("0")

    elif schema_type == "boolean":
        default = schema.get("default")
        if default is not None:
            lines.append(str(default).lower())
        else:
            lines.append("false")

    elif schema_type == "null":
        lines.append("null")

    else:
        # Unknown type or anyOf/oneOf
        if "anyOf" in schema or "oneOf" in schema:
            lines.append('"value"')
        else:
            lines.append('""')

    return lines


def _generate_plugin_markdown_doc(plugin_name: str, plugin_spec: Any) -> str:
    """Generate markdown documentation for a plugin with enhanced formatting."""
    from pydantic_core import PydanticUndefined

    lines = [f"# {plugin_name}", ""]

    # Overview section
    if plugin_spec.description:
        lines.extend(["## Overview", "", plugin_spec.description.strip(), ""])

    # Configuration section
    lines.append("## Configuration")
    lines.append("")

    if plugin_spec.config_model:
        # Get JSON schema for the model
        json_schema = plugin_spec.config_model.model_json_schema()
        properties = json_schema.get("properties", {})

        # YAML example
        lines.append("### Example Configuration")
        lines.append("")
        lines.append("```yaml")
        lines.append("pipeline:")
        lines.append(f'  - plugin: "{plugin_name}"')
        lines.append("    config:")

        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            # Get field schema
            field_schema = properties.get(field_name, {})

            # Get default value
            default = field_info.default

            # Generate YAML value using schema
            if default is PydanticUndefined:
                # Required field - generate example from schema
                yaml_lines = _generate_yaml_value_from_schema(field_schema, indent=2)
            elif default is None:
                yaml_lines = ["null"]
            elif isinstance(default, str):
                yaml_lines = [f'"{default}"']
            elif isinstance(default, bool):
                yaml_lines = [str(default).lower()]
            elif isinstance(default, (int, float)):
                yaml_lines = [str(default)]
            elif isinstance(default, list):
                # Use schema to generate example list
                yaml_lines = _generate_yaml_value_from_schema(field_schema, indent=2)
            elif isinstance(default, dict):
                # Use schema to generate example dict
                yaml_lines = _generate_yaml_value_from_schema(field_schema, indent=2)
            else:
                yaml_lines = [str(default)]

            # Get field type for comment
            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation))
            field_type = field_type.replace("typing.", "")

            # Get description
            description = field_info.description or ""

            # Build inline comment for first line
            if description:
                comment = f"  # {field_type}: {description}"
            else:
                comment = f"  # {field_type}"

            # Output YAML lines
            if len(yaml_lines) == 1 and not yaml_lines[0].startswith("\n"):
                # Simple single-line value
                lines.append(f"      {field_name}: {yaml_lines[0]}{comment}")
            else:
                # Multi-line value (nested structure)
                lines.append(f"      {field_name}:{comment}")
                for yaml_line in yaml_lines:
                    if yaml_line:  # Skip empty strings
                        lines.append(f"    {yaml_line}")

        lines.append("```")
        lines.append("")

        # Field reference table
        lines.append("### Field Reference")
        lines.append("")
        lines.append("| Field | Type | Default | Description |")
        lines.append("|-------|------|---------|-------------|")

        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            # Get default value for table
            default = field_info.default
            if default is PydanticUndefined:
                default_str = "*required*"
            elif default is None:
                default_str = "`null`"
            elif isinstance(default, str):
                default_str = f'`"{default}"`'
            elif isinstance(default, bool):
                default_str = f"`{str(default).lower()}`"
            else:
                default_str = f"`{default}`"

            # Get field type
            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation))
            field_type = field_type.replace("typing.", "")

            # Get description
            description = field_info.description or ""

            lines.append(f"| `{field_name}` | `{field_type}` | {default_str} | {description} |")

        lines.append("")
    else:
        lines.append("This plugin has no configuration options.")
        lines.append("")

    # CLI Usage section
    lines.append("## CLI Usage")
    lines.append("")
    lines.append("```bash")
    lines.append("# Run with default configuration")
    lines.append(f'nexus plugin "{plugin_name}" --case mycase')
    lines.append("")
    if plugin_spec.config_model:
        lines.append("# Run with custom configuration")
        lines.append(f'nexus plugin "{plugin_name}" --case mycase \\')
        example_fields = list(plugin_spec.config_model.model_fields.keys())[:2]
        for i, field in enumerate(example_fields):
            if i < len(example_fields) - 1:
                lines.append(f"  -C {field}=value \\")
            else:
                lines.append(f"  -C {field}=value")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def _generate_plugin_index_markdown(plugins: Dict[str, Any]) -> str:
    lines = ["# Nexus Plugins", "", f"Documented {len(plugins)} plugin(s).", ""]
    for name in sorted(plugins.keys()):
        safe_name = name.replace(" ", "_").lower()
        lines.append(f"- [{name}](plugins/{safe_name}.md)")
    lines.append("")
    lines.append("Generated by `nexus doc`.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrypoint


def main() -> None:
    """Console script entrypoint."""
    cli()


if __name__ == "__main__":
    main()


