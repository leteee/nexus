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
    if not plugin:
        click.echo(cli.get_help(click.Context(cli)))
        return

    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    from .core.discovery import get_plugin

    try:
        spec = get_plugin(plugin)
    except KeyError as exc:
        click.echo(f"ERROR: {exc}")
        sys.exit(1)

    click.echo(f"Plugin: {plugin}")
    if spec.description:
        click.echo(spec.description)
    if spec.config_model:
        click.echo("Configuration fields:")
        for field_name, field_info in spec.config_model.model_fields.items():
            default = field_info.default if field_info.default is not None else "<required>"
            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation))
            click.echo(f"  - {field_name} ({field_type}): {default}")


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


def _generate_plugin_markdown_doc(plugin_name: str, plugin_spec: Any) -> str:
    lines = [f"# {plugin_name}", ""]
    if plugin_spec.description:
        lines.extend([plugin_spec.description.strip(), ""])

    lines.append("## Configuration")
    lines.append("")

    if plugin_spec.config_model:
        for field_name, field_info in plugin_spec.config_model.model_fields.items():
            default = field_info.default if field_info.default is not None else "<required>"
            field_type = getattr(field_info.annotation, "__name__", str(field_info.annotation))
            lines.append(f"- **{field_name}** (*{field_type}*): {default}")
    else:
        lines.append("This plugin has no configuration options.")

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


