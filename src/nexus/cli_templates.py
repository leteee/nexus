"""
Template management CLI commands.

Provides commands for listing and inspecting templates.
"""

import json
import sys
import re
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .core.case_manager import CaseManager


console = Console()


@click.group(name="templates", invoke_without_command=True)
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.pass_context
def templates_cmd(ctx, format: str):
    """List and inspect templates."""
    # If no subcommand, default to list
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_templates_cmd, format=format)


@templates_cmd.command(name="list")
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.pass_context
def list_templates_cmd(ctx, format: str):
    """List all available templates with absolute paths."""
    from .cli import _load_case_manager, find_project_root

    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    templates = manager.list_available_templates()

    if not templates:
        console.print("[yellow]No templates found[/yellow]")
        console.print(f"\n[dim]Create templates in: {manager.templates_roots[0]}[/dim]")
        return

    # Get absolute paths for all templates
    template_info = {}
    for template_name in templates:
        try:
            template_path = manager._find_template(template_name)
            # Get relative path from project root
            try:
                rel_path = template_path.relative_to(project_root)
                relative = str(rel_path)
            except ValueError:
                relative = str(template_path)

            template_info[template_name] = {
                "name": template_name,
                "path": str(template_path),
                "relative": relative,
            }
        except FileNotFoundError:
            continue

    if format == "json":
        click.echo(json.dumps(template_info, indent=2))

    elif format == "yaml":
        import yaml
        click.echo(yaml.dump({"templates": template_info}, default_flow_style=False, allow_unicode=True))

    else:
        # Table format
        table = Table(title=f"Available Templates ({len(templates)})", show_header=True, header_style="bold magenta")
        table.add_column("Template", style="cyan", no_wrap=True)
        table.add_column("Absolute Path", style="dim")

        for template_name in sorted(templates):
            info = template_info.get(template_name)
            if info:
                # Truncate path if too long
                path = info["path"]
                if len(path) > 60:
                    path = path[:57] + "..."
                table.add_row(template_name, path)

        console.print(table)
        console.print("")
        console.print("[dim]💡 Tip: Use 'nexus templates show <name>' for detailed information[/dim]")


@templates_cmd.command(name="show")
@click.argument("template_name")
@click.pass_context
def show_template_cmd(ctx, template_name: str):
    """Show detailed information about a template."""
    from .cli import _load_case_manager, find_project_root, _discover
    from .core.discovery import list_plugins
    import yaml

    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    try:
        template_path = manager._find_template(template_name)
    except FileNotFoundError:
        console.print(f"[red]ERROR: Template '{template_name}' not found[/red]")
        console.print("\n[dim]Run 'nexus templates' to see available templates[/dim]")
        sys.exit(1)

    # Get relative path from project root
    try:
        rel_path = template_path.relative_to(project_root)
        relative = str(rel_path)
    except ValueError:
        relative = str(template_path)

    # Display template information
    console.print(Panel(f"[bold cyan]Template: {template_name}[/bold cyan]", expand=False))
    console.print()

    console.print("[bold]Absolute Path[/bold]")
    console.print(f"  {template_path}")
    console.print()

    console.print("[bold]Source[/bold]")
    console.print(f"  {relative} (relative to project root)")
    console.print()

    # Configuration preview
    console.print("[bold]Configuration Preview[/bold]")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
            config_data = yaml.safe_load(config_content)

            # Truncate if too long
            lines = config_content.split('\n')
            if len(lines) > 30:
                preview = '\n'.join(lines[:30]) + '\n...'
            else:
                preview = config_content

        console.print(Panel(preview, border_style="dim"))
        console.print()

        # Extract plugins used
        if config_data and "pipeline" in config_data:
            console.print("[bold]Plugins Used[/bold]")
            pipeline = config_data["pipeline"]
            for step in pipeline:
                if "plugin" in step:
                    plugin_name = step["plugin"]
                    console.print(f"  • {plugin_name}")
            console.print()

    except Exception as e:
        console.print(f"[red]Error reading template: {e}[/red]")
        console.print()

    # Quick start
    console.print("[bold]Quick Start[/bold]")
    console.print(f"  nexus run -c mycase -t {template_name}")
    console.print()
