"""
Plugin management CLI commands.

Provides commands for listing, inspecting, and searching plugins.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from .core.discovery import discover_all_plugins, list_plugins, get_plugin
from .core.formatter import PluginInfo, PluginFormatter


console = Console()


@click.group(name="plugins")
def plugins_cmd():
    """Manage and inspect Nexus plugins."""
    pass


@plugins_cmd.command(name="list")
@click.option("--tag", help="Filter plugins by tag")
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.pass_context
def list_plugins_cmd(ctx, tag: str, format: str):
    """List all available plugins."""
    from .cli import _discover, find_project_root

    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    plugins = list_plugins()
    if not plugins:
        console.print("[yellow]No plugins registered[/yellow]")
        return

    # Filter by tag if specified
    if tag:
        plugins = {
            name: spec
            for name, spec in plugins.items()
            if tag in (spec.tags or [])
        }
        if not plugins:
            console.print(f"[yellow]No plugins found with tag '{tag}'[/yellow]")
            return

    if format == "json":
        plugin_data = {
            name: PluginInfo(spec).to_dict()
            for name, spec in plugins.items()
        }
        click.echo(json.dumps(plugin_data, indent=2))

    elif format == "yaml":
        import yaml
        plugin_data = {
            name: PluginInfo(spec).to_dict()
            for name, spec in plugins.items()
        }
        click.echo(yaml.dump({"plugins": plugin_data}, default_flow_style=False, allow_unicode=True))

    else:
        # Table format
        title = f"Plugins with tag '{tag}' ({len(plugins)})" if tag else f"Available Plugins ({len(plugins)})"

        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Tags", style="green")
        table.add_column("Config", justify="center")
        table.add_column("Description", style="dim")

        for name, spec in sorted(plugins.items()):
            tags_str = ", ".join(spec.tags) if spec.tags else ""
            config_str = "✓" if spec.config_model else ""
            # Truncate description
            desc = (spec.description or "").split("\n")[0]
            if len(desc) > 60:
                desc = desc[:57] + "..."

            table.add_row(name, tags_str, config_str, desc)

        console.print(table)
        console.print("")
        console.print("[dim]💡 Tip: Use 'nexus plugins show <name>' for detailed configuration[/dim]")
        if not tag:
            console.print("[dim]💡 Tip: Use '--tag <tag>' to filter by tag[/dim]")


@plugins_cmd.command(name="show")
@click.argument("plugin_name")
@click.option("--yaml-only", is_flag=True, help="Show only YAML template")
@click.pass_context
def show_plugin_cmd(ctx, plugin_name: str, yaml_only: bool):
    """Show detailed information about a plugin."""
    from .cli import _discover, find_project_root

    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    try:
        spec = get_plugin(plugin_name)
    except KeyError:
        console.print(f"[red]ERROR: Plugin '{plugin_name}' not found[/red]")
        console.print("\n[dim]Run 'nexus plugins list' to see available plugins[/dim]")
        sys.exit(1)

    info = PluginInfo(spec)

    if yaml_only:
        yaml_template = PluginFormatter.generate_yaml_template(info)
        click.echo(yaml_template)
        return

    # Full detailed view
    console.print(Panel(f"[bold cyan]{info.name}[/bold cyan]", expand=False))
    console.print()

    # Tags
    if info.tags:
        console.print(f"[bold]Tags:[/bold] {', '.join(f'[green]{tag}[/green]' for tag in info.tags)}")
        console.print()

    # Description
    if info.description:
        console.print("[bold]Description:[/bold]")
        console.print(info.description)
        console.print()

    # Configuration Parameters
    if info.has_config and info.fields:
        console.print("[bold]Configuration Parameters:[/bold]")
        console.print()

        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Field", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Required", justify="center")
        table.add_column("Default")
        table.add_column("Description", style="dim")

        for field in info.fields:
            required_str = "✓" if field["required"] else ""
            default_str = "-" if field["required"] else str(field["default"])
            if len(default_str) > 30:
                default_str = default_str[:27] + "..."

            table.add_row(
                field["name"],
                field["type"],
                required_str,
                default_str,
                field["description"]
            )

        console.print(table)
        console.print()

    # YAML Template
    console.print("[bold]YAML Template:[/bold]")
    console.print()
    yaml_template = PluginFormatter.generate_yaml_template(info)
    from rich.syntax import Syntax
    syntax = Syntax(yaml_template, "yaml", theme="monokai", line_numbers=False)
    console.print(syntax)
    console.print()

    # Quick Start
    console.print("[bold]Quick Start:[/bold]")
    console.print()
    console.print(f'  [dim]# Execute directly[/dim]')
    console.print(f'  nexus exec "{info.name}" -c mycase')
    console.print()
    console.print(f'  [dim]# Or add to case.yaml[/dim]')
    console.print(f'  nexus run -c mycase')
    console.print()


@plugins_cmd.command(name="search")
@click.argument("keyword")
@click.pass_context
def search_plugins_cmd(ctx, keyword: str):
    """Search plugins by keyword in name, description, or tags."""
    from .cli import _discover, find_project_root

    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    plugins = list_plugins()
    keyword_lower = keyword.lower()

    # Search in name, description, and tags
    matches = {}
    for name, spec in plugins.items():
        match_type = None
        if keyword_lower in name.lower():
            match_type = "name"
        elif spec.description and keyword_lower in spec.description.lower():
            match_type = "description"
        elif spec.tags and any(keyword_lower in tag.lower() for tag in spec.tags):
            match_type = "tag"

        if match_type:
            matches[name] = (spec, match_type)

    if not matches:
        console.print(f"[yellow]No plugins found matching '{keyword}'[/yellow]")
        return

    table = Table(title=f"Search results for '{keyword}' ({len(matches)} matches)", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Match", style="green")
    table.add_column("Description", style="dim")

    for name, (spec, match_type) in sorted(matches.items()):
        desc = (spec.description or "").split("\n")[0]
        if len(desc) > 60:
            desc = desc[:57] + "..."
        table.add_row(name, match_type, desc)

    console.print(table)
    console.print()
    console.print("[dim]💡 Tip: Use 'nexus plugins show <name>' for detailed information[/dim]")


@plugins_cmd.command(name="tags")
@click.pass_context
def list_tags_cmd(ctx):
    """List all plugin tags with usage statistics."""
    from .cli import _discover, find_project_root

    project_root = find_project_root(Path.cwd())
    _discover(project_root)

    plugins = list_plugins()

    # Count tags
    tag_counts = defaultdict(list)
    for name, spec in plugins.items():
        for tag in (spec.tags or []):
            tag_counts[tag].append(name)

    if not tag_counts:
        console.print("[yellow]No tags found[/yellow]")
        return

    table = Table(title="Plugin Tags Overview", show_header=True, header_style="bold magenta")
    table.add_column("Tag", style="green")
    table.add_column("Count", justify="right", style="cyan")
    table.add_column("Plugins", style="dim")

    for tag in sorted(tag_counts.keys()):
        plugin_names = tag_counts[tag]
        count = len(plugin_names)

        # Truncate plugin list if too long
        plugins_str = ", ".join(plugin_names)
        if len(plugins_str) > 50:
            plugins_str = plugins_str[:47] + "..."

        table.add_row(tag, str(count), plugins_str)

    console.print(table)
    console.print()
    console.print("[dim]💡 Tip: Use 'nexus plugins list --tag <tag>' to filter plugins[/dim]")
