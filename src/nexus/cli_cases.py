"""
Case management CLI commands.

Provides commands for listing and inspecting cases.
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from .core.case_manager import CaseManager


console = Console()


@click.group(name="cases", invoke_without_command=True)
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.pass_context
def cases_cmd(ctx, format: str):
    """List and inspect cases."""
    # If no subcommand, default to list
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_cases_cmd, format=format)


@cases_cmd.command(name="list")
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format")
@click.pass_context
def list_cases_cmd(ctx, format: str):
    """List all available cases with absolute paths."""
    from .cli import _load_case_manager, find_project_root

    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    cases = manager.list_existing_cases()

    if not cases:
        console.print("[yellow]No cases found[/yellow]")
        console.print("\n[dim]Create a case by running: nexus run -c <case_name> -t <template>[/dim]")
        return

    # Get absolute paths for all cases
    case_info = {}
    for case_name in cases:
        case_path = manager.resolve_case_path(case_name)
        config_file = case_path / "case.yaml"
        case_info[case_name] = {
            "name": case_name,
            "path": str(case_path),
            "config_file": str(config_file),
            "exists": config_file.exists(),
        }

    if format == "json":
        click.echo(json.dumps(case_info, indent=2))

    elif format == "yaml":
        import yaml
        click.echo(yaml.dump({"cases": case_info}, default_flow_style=False, allow_unicode=True))

    else:
        # Table format
        table = Table(title=f"Available Cases ({len(cases)})", show_header=True, header_style="bold magenta")
        table.add_column("Case", style="cyan", no_wrap=True)
        table.add_column("Absolute Path", style="dim")

        for case_name in sorted(cases):
            info = case_info[case_name]
            table.add_row(case_name, info["path"])

        console.print(table)
        console.print("")
        console.print("[dim]💡 Tip: Use 'nexus cases show <name>' for detailed information[/dim]")


@cases_cmd.command(name="show")
@click.argument("case_name")
@click.pass_context
def show_case_cmd(ctx, case_name: str):
    """Show detailed information about a case."""
    from .cli import _load_case_manager, find_project_root

    project_root = find_project_root(Path.cwd())
    manager = _load_case_manager(project_root)

    case_path = manager.resolve_case_path(case_name)
    config_file = case_path / "case.yaml"

    if not case_path.exists():
        console.print(f"[red]ERROR: Case directory not found: {case_path}[/red]")
        console.print("\n[dim]Run 'nexus cases' to see available cases[/dim]")
        sys.exit(1)

    if not config_file.exists():
        console.print(f"[red]ERROR: case.yaml not found in: {case_path}[/red]")
        console.print("\n[dim]Create case.yaml or use a template: nexus run -c {case_name} -t <template>[/dim]")
        sys.exit(1)

    # Display case information
    console.print(Panel(f"[bold cyan]Case: {case_name}[/bold cyan]", expand=False))
    console.print()

    console.print("[bold]Absolute Path[/bold]")
    console.print(f"  {case_path}")
    console.print()

    console.print("[bold]Configuration File[/bold]")
    console.print(f"  {config_file}")
    console.print()

    # Directory tree
    console.print("[bold]Directory Contents[/bold]")
    tree = Tree(f"[cyan]{case_name}/[/cyan]")

    # List directory contents (max 2 levels)
    def add_tree_items(parent, path, level=0, max_level=2):
        if level >= max_level:
            return
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_file(), p.name))
            for item in items[:20]:  # Limit to 20 items
                if item.is_file():
                    parent.add(f"[dim]{item.name}[/dim]")
                elif item.is_dir():
                    branch = parent.add(f"[cyan]{item.name}/[/cyan]")
                    add_tree_items(branch, item, level + 1, max_level)
        except PermissionError:
            parent.add("[red]<Permission Denied>[/red]")

    add_tree_items(tree, case_path)
    console.print(tree)
    console.print()

    # Configuration preview
    console.print("[bold]Configuration Preview[/bold]")
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_content = f.read()
            # Truncate if too long
            lines = config_content.split('\n')
            if len(lines) > 30:
                preview = '\n'.join(lines[:30]) + '\n...'
            else:
                preview = config_content
        console.print(Panel(preview, border_style="dim"))
    except Exception as e:
        console.print(f"[red]Error reading configuration: {e}[/red]")
    console.print()

    # Quick start
    console.print("[bold]Quick Start[/bold]")
    console.print(f"  nexus run -c {case_name}")
    console.print()
