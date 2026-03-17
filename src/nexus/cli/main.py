"""
Command line interface for the streamlined Nexus runtime.

The CLI now focuses purely on plugin orchestration without the legacy
DataSource/handler features.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click

from ..core.config import load_system_configuration
from ..core.discovery import list_plugins
from ..core.engine import PipelineEngine
from .cases import cases_cmd
from .plugins import plugins_cmd
from .templates import templates_cmd
from .utils import (
    discover_plugins,
    find_project_root,
    load_case_manager,
    parse_config_overrides,
    setup_logging,
)


@click.group(invoke_without_command=True, help="Nexus - A modern data processing framework")
@click.option("--version", is_flag=True, help="Show version information")
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    if version:
        from .. import __version__

        click.echo(f"Nexus {__version__}")
        return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Register plugin management commands
cli.add_command(plugins_cmd)

# Register workspace management commands
cli.add_command(cases_cmd)
cli.add_command(templates_cmd)


@cli.command()
@click.option("--case", "-c", required=True, help="Case directory (relative or absolute)")
@click.option("--template", "-t", help="Template to use (optional)")
@click.option("--config", "-C", multiple=True, help="Config overrides (key=value)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def run(case: str, template: Optional[str], config: tuple[str, ...], verbose: bool) -> None:
    project_root = find_project_root(Path.cwd())
    system_overrides, business_overrides = parse_config_overrides(config)
    system_config = load_system_configuration(project_root, system_overrides)
    log_level = "DEBUG" if verbose else system_config.get("logging", {}).get("level", "INFO")
    log_config_path = system_config.get("logging", {}).get("config_path")
    setup_logging(log_level, project_root, log_config_path)

    manager = load_case_manager(project_root, system_config)

    try:
        _config_path, case_config = manager.get_case_config(case, template)
    except Exception as exc:  # pylint: disable=broad-except
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    engine = PipelineEngine(project_root, manager.resolve_case_path(case), system_config)
    try:
        engine.run_pipeline(case_config, business_overrides)
        click.echo(f"SUCCESS: Pipeline completed for case '{case}'")
    except Exception as exc:  # pylint: disable=broad-except
        click.echo(f"ERROR: {exc}", err=True)
        if verbose:
            raise
        sys.exit(1)


@cli.command(name="exec")
@click.argument("plugin_name")
@click.option("--case", "-c", required=True, help="Case directory for execution context")
@click.option("--config", "-C", multiple=True, help="Config overrides (key=value)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def exec_cmd(plugin_name: str, case: str, config: tuple[str, ...], verbose: bool) -> None:
    """Execute a single plugin."""
    project_root = find_project_root(Path.cwd())
    system_overrides, business_overrides = parse_config_overrides(config)
    system_config = load_system_configuration(project_root, system_overrides)
    log_level = "DEBUG" if verbose else system_config.get("logging", {}).get("level", "INFO")
    log_config_path = system_config.get("logging", {}).get("config_path")
    setup_logging(log_level, project_root, log_config_path)

    manager = load_case_manager(project_root, system_config)
    engine = PipelineEngine(project_root, manager.resolve_case_path(case), system_config)

    try:
        result = engine.run_single_plugin(plugin_name, business_overrides)
    except Exception as exc:  # pylint: disable=broad-except
        click.echo(f"ERROR: {exc}", err=True)
        if verbose:
            raise
        sys.exit(1)

    click.echo(f"SUCCESS: Plugin '{plugin_name}' completed")
    if result is not None:
        click.echo(f"Result type: {type(result).__name__}")


@cli.command(name="doc")
@click.option("--output", type=click.Path(), default="docs/api", help="Output directory (default: docs/api)")
@click.option("--force", "-f", is_flag=True, help="Force overwrite without confirmation")
def doc_cmd(output: str, force: bool) -> None:
    project_root = find_project_root(Path.cwd())
    system_config = load_system_configuration(project_root)
    discover_plugins(project_root, system_config)

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


# Documentation helpers (unchanged)
def _generate_yaml_value_from_schema(schema: dict, indent: int = 0) -> list[str]:
    from typing import Any as _Any  # keep import local

    lines = []
    schema_type = schema.get("type")

    if schema_type == "array":
        items_schema = schema.get("items", {})
        items_type = items_schema.get("type")

        if items_type == "object":
            lines.append("")
            properties = items_schema.get("properties", {})
            if properties:
                indent_str = "  " * (indent + 1)
                lines.append(f"{indent_str}- # Example item")
                for prop_name, prop_schema in properties.items():
                    prop_lines = _generate_yaml_value_from_schema(prop_schema, indent + 2)
                    if len(prop_lines) == 1 and not prop_lines[0].startswith("\n"):
                        lines.append(f"{indent_str}  {prop_name}: {prop_lines[0]}")
                    else:
                        lines.append(f"{indent_str}  {prop_name}:{prop_lines[0]}")
                        lines.extend(prop_lines[1:])
            else:
                indent_str = "  " * (indent + 1)
                lines.append(f"{indent_str}- # Example item (dict)")
                lines.append(f"{indent_str}  key1: \"value1\"")
                lines.append(f"{indent_str}  key2: \"value2\"")
        elif items_type == "string":
            lines.append("")
            indent_str = "  " * (indent + 1)
            lines.append(f"{indent_str}- \"item1\"")
            lines.append(f"{indent_str}- \"item2\"")
        elif items_type in {"number", "integer"}:
            lines.append("")
            indent_str = "  " * (indent + 1)
            lines.append(f"{indent_str}- 1")
            lines.append(f"{indent_str}- 2")
        else:
            lines.append(" []")

    elif schema_type == "object":
        properties = schema.get("properties", {})
        if properties:
            lines.append("")
            indent_str = "  " * (indent + 1)
            for prop_name, prop_schema in properties.items():
                prop_lines = _generate_yaml_value_from_schema(prop_schema, indent + 1)
                if len(prop_lines) == 1 and not prop_lines[0].startswith("\n"):
                    lines.append(f"{indent_str}{prop_name}: {prop_lines[0]}")
                else:
                    lines.append(f"{indent_str}{prop_name}:{prop_lines[0]}")
                    lines.extend(prop_lines[1:])
        else:
            lines.append(" {}")

    elif schema_type == "string":
        default = schema.get("default")
        lines.append(f'"{default}"' if default else '"value"')

    elif schema_type in {"number", "integer"}:
        default = schema.get("default")
        lines.append(str(default) if default is not None else "0")

    elif schema_type == "boolean":
        default = schema.get("default")
        lines.append(str(default).lower() if default is not None else "false")

    elif schema_type == "null":
        lines.append("null")
    else:
        lines.append('"value"')

    return lines


def _generate_plugin_markdown_doc(plugin_name: str, plugin_spec: Any) -> str:
    from pydantic_core import PydanticUndefined

    lines = [f"# {plugin_name}", ""]

    if plugin_spec.description:
        lines.extend(["## Overview", "", plugin_spec.description.strip(), ""])

    lines.append("## Configuration")
    lines.append("")

    if plugin_spec.config_model:
        json_schema = plugin_spec.config_model.model_json_schema()
        properties = json_schema.get("properties", {})

        lines.append("### Example Configuration")
        lines.append("")
        lines.append("```yaml")
        lines.append("pipeline:")
        lines.append(f'  - plugin: "{plugin_name}"')
        lines.append("    config:")

        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            field_schema = properties.get(field_name, {})
            default = field_info.default

            if default is PydanticUndefined:
                yaml_lines = _generate_yaml_value_from_schema(field_schema, indent=2)
            elif default is None:
                yaml_lines = ["null"]
            elif isinstance(default, str):
                yaml_lines = [f'"{default}"']
            elif isinstance(default, bool):
                yaml_lines = [str(default).lower()]
            elif isinstance(default, (int, float)):
                yaml_lines = [str(default)]
            elif isinstance(default, (list, dict)):
                yaml_lines = _generate_yaml_value_from_schema(field_schema, indent=2)
            else:
                yaml_lines = [str(default)]

            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation)).replace("typing.", "")
            description = field_info.description or ""
            comment = f"  # {field_type}: {description}" if description else f"  # {field_type}"

            if len(yaml_lines) == 1 and not yaml_lines[0].startswith("\n"):
                lines.append(f"      {field_name}: {yaml_lines[0]}{comment}")
            else:
                lines.append(f"      {field_name}:{comment}")
                for yaml_line in yaml_lines:
                    if yaml_line:
                        lines.append(f"    {yaml_line}")

        lines.append("```")
        lines.append("")

        lines.append("### Field Reference")
        lines.append("")
        lines.append("| Field | Type | Default | Description |")
        lines.append("|-------|------|---------|-------------|")

        for field_name, field_info in plugin_spec.config_model.model_fields.items():
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

            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation)).replace("typing.", "")
            description = field_info.description or ""

            lines.append(f"| `{field_name}` | `{field_type}` | {default_str} | {description} |")

        lines.append("")
    else:
        lines.append("This plugin has no configuration options.")
        lines.append("")

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
            lines.append(f"  -C {field}=value" + (" \\" if i < len(example_fields) - 1 else ""))
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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
