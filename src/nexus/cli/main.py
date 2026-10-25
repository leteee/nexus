"""Command line interface for Nexus 2.0."""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from nexus import __version__
from nexus.core.config import (
    EngineSettings,
    detect_project_root,
    load_settings,
    parse_cli_set,
)
from nexus.core.engine import Engine
from nexus.core.errors import NexusError
from nexus.core.registry import NodeSpec
from nexus.core.utils import format_duration, json_dumps

console = Console()


@dataclass
class CliState:
    project_root: Path
    config_files: tuple[str, ...]
    verbose: bool


def configure_logging(level: str, log_file: str | None, *, project_root: Path, rich: bool = True) -> None:
    root = logging.getLogger("nexus")
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    handler: logging.Handler
    if rich:
        handler = RichHandler(console=Console(stderr=True), rich_tracebacks=True, show_path=False, markup=False)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s") if rich else logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    root.addHandler(handler)

    if log_file:
        path = Path(log_file).expanduser()
        if not path.is_absolute():
            path = project_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root.addHandler(file_handler)


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    help="Nexus - a configurable, orchestratable Python logic execution engine.",
)
@click.option(
    "--project",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Project root (defaults to the nearest pyproject.toml/.git/config/nexus.yaml).",
)
@click.option(
    "--config-file",
    multiple=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Extra engine config file layered after config/nexus.yaml.",
)
@click.option("--version", "show_version", is_flag=True, help="Show version and exit.")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging and tracebacks.")
@click.pass_context
def cli(
    ctx: click.Context,
    project: Path | None,
    config_file: tuple[Path, ...],
    show_version: bool,
    verbose: bool,
) -> None:
    if show_version:
        click.echo(f"Nexus {__version__}")
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    project_root = detect_project_root(project) if project else detect_project_root()
    ctx.obj = CliState(
        project_root=project_root,
        config_files=tuple(str(path) for path in config_file),
        verbose=verbose,
    )


def _settings(
    state: CliState,
    *,
    overrides: dict[str, Any] | None = None,
) -> EngineSettings:
    return load_settings(
        state.project_root,
        config_files=list(state.config_files),
        overrides=overrides,
    )


def _engine(state: CliState, settings: EngineSettings) -> Engine:
    if state.verbose:
        settings.logging.level = "DEBUG"
    configure_logging(
        settings.logging.level,
        settings.logging.file,
        project_root=settings.project_root,
        rich=settings.logging.rich,
    )
    return Engine(settings=settings)


def _fail(message: str, *, verbose: bool = False, exc: BaseException | None = None, code: int = 1) -> None:
    console.print(f"[bold red]ERROR[/bold red] {message}")
    if verbose and exc is not None:
        console.print(Panel(traceback.format_exc(), title="traceback", border_style="red"))
    raise SystemExit(code)


def _print_run_summary(result: Any) -> None:
    color = {"success": "green", "failed": "red", "cancelled": "yellow"}.get(result.status.value, "white")
    console.print(
        f"[bold]{result.flow}[/bold]  "
        f"[{color}]{result.status.value}[/{color}]  "
        f"[dim]{result.run_id}  {format_duration(result.duration_ms)}[/dim]"
    )
    if result.error:
        console.print(f"[red]{result.error}[/red]")

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Step", style="cyan", no_wrap=True)
    table.add_column("Node", style="dim")
    table.add_column("Status")
    table.add_column("Time", justify="right")
    table.add_column("Attempts", justify="right")
    for step_id, step in result.steps.items():
        status_color = {
            "success": "green",
            "failed": "red",
            "skipped": "yellow",
            "cancelled": "yellow",
        }.get(step.status.value, "white")
        table.add_row(
            step_id,
            step.use,
            f"[{status_color}]{step.status.value}[/{status_color}]",
            format_duration(step.duration_ms),
            str(step.attempts),
        )
    console.print(table)

    if result.outputs:
        console.print("[bold]Outputs[/bold]")
        for key, value in result.outputs.items():
            console.print(f"  [cyan]{key}[/cyan] = {json_dumps(value, indent=None)[:300]}")


@cli.command()
@click.argument("flow")
@click.option("-w", "--workdir", type=click.Path(path_type=Path), default=None, help="Working directory for relative paths.")
@click.option("-s", "--set", "variables", multiple=True, help="Override a flow variable: key=value (repeatable).")
@click.option("--max-workers", type=click.IntRange(1, 256), default=None, help="Override execution.max_workers.")
@click.option("--strategy", type=click.Choice(["sequential", "dag"]), default=None, help="Override execution strategy.")
@click.option("--no-fail-fast", is_flag=True, help="Keep scheduling independent steps after a failure.")
@click.option("--dry-run", is_flag=True, help="Validate and show the plan without executing nodes.")
@click.option("--json", "as_json", is_flag=True, help="Print the run result as JSON.")
@click.pass_obj
def run(
    state: CliState,
    flow: str,
    workdir: Path | None,
    variables: tuple[str, ...],
    max_workers: int | None,
    strategy: str | None,
    no_fail_fast: bool,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Execute a flow (path or name discovered under flow_paths)."""

    execution_overrides: dict[str, Any] = {}
    if max_workers is not None:
        execution_overrides["max_workers"] = max_workers
    if strategy is not None:
        execution_overrides["strategy"] = strategy
    if no_fail_fast:
        execution_overrides["fail_fast"] = False

    try:
        settings = _settings(state)
        engine = _engine(state, settings)
        parsed_vars = parse_cli_set(variables)
        result = engine.run(
            flow,
            workdir=workdir,
            variables=parsed_vars,
            dry_run=dry_run,
            execution=execution_overrides,
        )
    except NexusError as exc:
        _fail(str(exc), verbose=state.verbose, exc=exc)
    except Exception as exc:  # pragma: no cover - unexpected
        _fail(f"{type(exc).__name__}: {exc}", verbose=state.verbose, exc=exc)

    if as_json:
        click.echo(json_dumps(result))
    else:
        _print_run_summary(result)
    raise SystemExit(0 if result.ok else 1)


@cli.command()
@click.argument("flow")
@click.option("--json", "as_json", is_flag=True, help="Print validation errors as JSON.")
@click.pass_obj
def validate(state: CliState, flow: str, as_json: bool) -> None:
    """Validate a flow without executing it."""

    try:
        settings = _settings(state)
        engine = _engine(state, settings)
        errors = engine.validate(flow)
        graph = engine.plan(flow) if not errors else None
    except NexusError as exc:
        _fail(str(exc), verbose=state.verbose, exc=exc)
    except Exception as exc:  # pragma: no cover
        _fail(f"{type(exc).__name__}: {exc}", verbose=state.verbose, exc=exc)

    if as_json:
        click.echo(json_dumps({"ok": not errors, "errors": errors}))
    elif errors:
        console.print(f"[bold red]INVALID[/bold red] {flow}")
        for error in errors:
            console.print(f"  - {error}")
    else:
        assert graph is not None
        console.print(
            f"[bold green]OK[/bold green] {graph.flow.name}: "
            f"{len(graph.steps)} steps, {len(graph.levels)} level(s), strategy={graph.flow.execution.strategy}"
        )
    raise SystemExit(0 if not errors else 1)


@cli.command()
@click.argument("flow")
@click.option("--format", "output_format", type=click.Choice(["table", "mermaid", "json"]), default="table")
@click.pass_obj
def plan(state: CliState, flow: str, output_format: str) -> None:
    """Show the execution plan (dependency levels) for a flow."""

    try:
        settings = _settings(state)
        engine = _engine(state, settings)
        graph = engine.plan(flow)
    except NexusError as exc:
        _fail(str(exc), verbose=state.verbose, exc=exc)

    if output_format == "json":
        click.echo(json_dumps(graph.to_dict()))
        return
    if output_format == "mermaid":
        click.echo(graph.to_mermaid())
        return

    console.print(f"[bold]{graph.flow.name}[/bold]  strategy={graph.flow.execution.strategy}")
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Level", justify="right", style="dim")
    table.add_column("Step", style="cyan")
    table.add_column("Node", style="dim")
    table.add_column("Depends on")
    for index, level in enumerate(graph.levels):
        for step_id in level:
            step = graph.steps[step_id]
            table.add_row(
                str(index),
                step_id,
                step.use,
                ", ".join(sorted(graph.dependencies[step_id])) or "-",
            )
    console.print(table)


@cli.group(name="nodes")
def nodes_cmd() -> None:
    """Inspect registered node types."""


@nodes_cmd.command(name="list")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
@click.pass_obj
def nodes_list(state: CliState, tag: str | None, output_format: str) -> None:
    """List registered nodes."""

    try:
        settings = _settings(state)
        engine = _engine(state, settings)
        specs = engine.registry.list(tag=tag)
    except NexusError as exc:
        _fail(str(exc), verbose=state.verbose, exc=exc)

    if output_format == "json":
        click.echo(json_dumps([spec.describe() for spec in specs]))
        return

    table = Table(
        title=f"Nodes ({len(specs)})" + (f" tagged '{tag}'" if tag else ""),
        show_header=True,
        header_style="bold",
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Tags", style="green")
    table.add_column("Inputs", justify="center")
    table.add_column("Description", style="dim")
    for spec in specs:
        table.add_row(
            spec.name,
            ", ".join(spec.tags),
            "yes" if spec.input_model else "",
            (spec.description or "").splitlines()[0] if spec.description else "",
        )
    console.print(table)
    if engine.registry.load_errors:
        console.print("[yellow]Optional packs that could not be loaded:[/yellow]")
        for error in engine.registry.load_errors:
            console.print(f"  - {error}")


@nodes_cmd.command(name="show")
@click.argument("name")
@click.option("--yaml", "as_yaml", is_flag=True, help="Print only an example YAML step.")
@click.pass_obj
def nodes_show(state: CliState, name: str, as_yaml: bool) -> None:
    """Show a node's schema and an example step."""

    try:
        settings = _settings(state)
        engine = _engine(state, settings)
        spec = engine.registry.get(name)
    except NexusError as exc:
        _fail(str(exc), verbose=state.verbose, exc=exc)

    snippet = example_step(spec)
    if as_yaml:
        click.echo(snippet)
        return

    console.print(Panel(f"[bold cyan]{spec.name}[/bold cyan]", expand=False))
    if spec.tags:
        console.print(f"[bold]Tags:[/bold] {', '.join(spec.tags)}")
    if spec.description:
        console.print(f"[bold]Description:[/bold]\n{spec.description}\n")
    console.print(f"[bold]Source:[/bold] {spec.source}")
    console.print(f"[bold]Version:[/bold] {spec.version}")

    if spec.input_model:
        table = Table(title="Inputs", show_header=True, header_style="bold")
        table.add_column("Field", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Required", justify="center")
        table.add_column("Default")
        table.add_column("Description", style="dim")
        for field_name, field_info in spec.input_model.model_fields.items():
            required = field_info.is_required()
            if required:
                default = "-"
            else:
                from pydantic_core import PydanticUndefined

                value = field_info.get_default(call_default_factory=True)
                default = "PydanticUndefined" if value is PydanticUndefined else repr(value)
            table.add_row(
                field_name,
                _type_name(field_info.annotation),
                "yes" if required else "",
                default,
                field_info.description or "",
            )
        console.print(table)
    else:
        console.print("[dim]This node accepts an untyped mapping.[/dim]")

    console.print("\n[bold]Example[/bold]")
    console.print(snippet)


@cli.group(name="config")
def config_cmd() -> None:
    """Inspect resolved engine configuration."""


@config_cmd.command(name="show")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), default="yaml")
@click.pass_obj
def config_show(state: CliState, output_format: str) -> None:
    """Show the merged engine configuration."""

    try:
        settings = _settings(state)
    except NexusError as exc:
        _fail(str(exc), verbose=state.verbose, exc=exc)
    data = settings.model_dump(mode="json")
    if output_format == "json":
        click.echo(json_dumps(data))
    else:
        import yaml

        click.echo(str(yaml.safe_dump(data, sort_keys=False, allow_unicode=True)))


@cli.command()
@click.argument("directory", type=click.Path(file_okay=False, path_type=Path), default=Path("."))
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def init(directory: Path, force: bool) -> None:
    """Create a minimal project with an example flow and config."""

    directory = directory.resolve()
    flows_dir = directory / "flows"
    config_dir = directory / "config"
    flow_path = flows_dir / "hello.yaml"
    config_path = config_dir / "nexus.yaml"

    if flow_path.exists() and not force:
        _fail(f"{flow_path} already exists; use --force to overwrite")
    if config_path.exists() and not force:
        _fail(f"{config_path} already exists; use --force to overwrite")

    flows_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    flow_path.write_text(
        """version: "2.0"
name: hello
description: A minimal Nexus flow.
steps:
  - id: greet
    use: core.python
    with:
      target: builtins.print
      args: ["Hello from Nexus 2.0"]
outputs:
  printed: "${steps.greet.result}"
""",
        encoding="utf-8",
    )
    config_path.write_text(
        """version: 2
execution:
  strategy: sequential
  max_workers: 1
logging:
  level: INFO
""",
        encoding="utf-8",
    )
    console.print(f"[green]Created[/green] {flow_path}")
    console.print(f"[green]Created[/green] {config_path}")
    console.print(f"Next: [cyan]nexus run {flow_path} -w {directory / 'runs' / 'hello'}[/cyan]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _type_name(annotation: Any) -> str:
    text = getattr(annotation, "__name__", str(annotation))
    return text.replace("typing.", "")


def _sample_value(annotation: Any, default: Any = None) -> Any:
    if default is not None:
        return default
    text = str(annotation)
    if "bool" in text:
        return True
    if "int" in text:
        return 1
    if "float" in text:
        return 1.0
    if "list" in text or "List" in text:
        return []
    if "dict" in text or "Dict" in text or "Mapping" in text:
        return {}
    return "value"


def example_step(spec: NodeSpec) -> str:
    import yaml
    from pydantic_core import PydanticUndefined

    payload: dict[str, Any] = {
        "id": "step_id",
        "use": spec.name,
    }
    if spec.input_model:
        inputs: dict[str, Any] = {}
        for field_name, field_info in spec.input_model.model_fields.items():
            if field_info.is_required():
                if field_name == "start_time":
                    inputs[field_name] = "2025-10-27 00:00:00"
                elif field_name == "end_time":
                    inputs[field_name] = "2025-10-27 00:00:10"
                else:
                    inputs[field_name] = _sample_value(field_info.annotation)
                continue
            default = field_info.get_default(call_default_factory=True)
            if default is not PydanticUndefined:
                inputs[field_name] = default
        if inputs:
            payload["with"] = inputs
    else:
        payload["with"] = {}
    return str(yaml.safe_dump([payload], sort_keys=False, allow_unicode=True)).strip()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
