from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from nexus.cli.main import cli


def write_flow(path: Path) -> None:
    path.write_text(
        """
version: "2.0"
name: cli-test
steps:
  - id: hello
    use: core.echo
    with:
      value: "hi"
outputs:
  value: "${steps.hello.value}"
""",
        encoding="utf-8",
    )


def test_run_json(tmp_path: Path) -> None:
    flow = tmp_path / "flow.yaml"
    write_flow(flow)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", str(tmp_path), "run", str(flow), "-w", str(tmp_path / "run"), "--json"],
    )
    assert result.exit_code == 0, result.output
    assert '"status": "success"' in result.output


def test_validate_and_plan(tmp_path: Path) -> None:
    flow = tmp_path / "flow.yaml"
    write_flow(flow)
    runner = CliRunner()
    validated = runner.invoke(cli, ["--project", str(tmp_path), "validate", str(flow)])
    assert validated.exit_code == 0, validated.output
    assert "OK" in validated.output

    planned = runner.invoke(cli, ["--project", str(tmp_path), "plan", str(flow), "--format", "json"])
    assert planned.exit_code == 0, planned.output
    assert '"hello"' in planned.output

    mermaid = runner.invoke(cli, ["--project", str(tmp_path), "plan", str(flow), "--format", "mermaid"])
    assert mermaid.exit_code == 0
    assert "flowchart TD" in mermaid.output


def test_nodes_and_config(tmp_path: Path) -> None:
    runner = CliRunner()
    listed = runner.invoke(cli, ["--project", str(tmp_path), "nodes", "list", "--format", "json"])
    assert listed.exit_code == 0, listed.output
    assert "core.echo" in listed.output

    shown = runner.invoke(cli, ["--project", str(tmp_path), "nodes", "show", "core.echo"])
    assert shown.exit_code == 0
    assert "core.echo" in shown.output

    snippet = runner.invoke(cli, ["--project", str(tmp_path), "nodes", "show", "core.python", "--yaml"])
    assert snippet.exit_code == 0, snippet.output
    assert "use: core.python" in snippet.output

    config = runner.invoke(cli, ["--project", str(tmp_path), "config", "show", "--format", "json"])
    assert config.exit_code == 0
    assert "execution" in config.output


def test_init(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--project", str(tmp_path), "init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "flows" / "hello.yaml").exists()
    assert (tmp_path / "config" / "nexus.yaml").exists()

    second = runner.invoke(cli, ["--project", str(tmp_path), "init", str(tmp_path)])
    assert second.exit_code != 0


def test_run_failure_exit_code(tmp_path: Path) -> None:
    flow = tmp_path / "fail.yaml"
    flow.write_text(
        """
version: "2.0"
name: fail
steps:
  - id: fail
    use: core.fail
    with:
      message: expected
""",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["--project", str(tmp_path), "run", str(flow), "-w", str(tmp_path / "run")])
    assert result.exit_code == 1
