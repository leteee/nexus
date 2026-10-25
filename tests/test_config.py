from __future__ import annotations

from pathlib import Path

import pytest

from nexus.core.config import load_settings, parse_cli_set, resolve_flow_path
from nexus.core.errors import ConfigError


def test_defaults_and_layering(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "nexus.yaml").write_text(
        "execution:\n  strategy: dag\n  max_workers: 2\nlogging:\n  level: DEBUG\n",
        encoding="utf-8",
    )
    (config / "nexus.local.yaml").write_text(
        "execution:\n  max_workers: 6\n",
        encoding="utf-8",
    )
    settings = load_settings(tmp_path, environ={})
    assert settings.execution.strategy == "dag"
    assert settings.execution.max_workers == 6
    assert settings.logging.level == "DEBUG"


def test_env_and_programmatic_overrides(tmp_path: Path) -> None:
    settings = load_settings(
        tmp_path,
        environ={"NEXUS__EXECUTION__MAX_WORKERS": "3", "NEXUS__LOGGING__LEVEL": "WARNING"},
        overrides={"execution": {"fail_fast": False}},
    )
    assert settings.execution.max_workers == 3
    assert settings.logging.level == "WARNING"
    assert settings.execution.fail_fast is False


def test_invalid_config_is_reported(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "nexus.yaml").write_text("execution:\n  max_workers: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(tmp_path, environ={})


def test_parse_cli_set_nested_and_timestamps() -> None:
    data = parse_cli_set(
        [
            "a.b=2",
            "flag=true",
            "items=[1, 2]",
            "start=2025-10-27 08:30:00",
        ]
    )
    assert data["a"]["b"] == 2
    assert data["flag"] is True
    assert data["items"] == [1, 2]
    assert isinstance(data["start"], str)


def test_parse_cli_set_rejects_bad_input() -> None:
    with pytest.raises(ConfigError):
        parse_cli_set(["missing"])
    with pytest.raises(ConfigError):
        parse_cli_set(["=1"])


def test_resolve_flow_path_by_name_and_nested(tmp_path: Path) -> None:
    flows = tmp_path / "flows"
    (flows / "nested").mkdir(parents=True)
    (flows / "hello.yaml").write_text("version: '2.0'\nsteps: []\n", encoding="utf-8")
    (flows / "nested" / "deep.yaml").write_text("version: '2.0'\nsteps: []\n", encoding="utf-8")
    settings = load_settings(tmp_path, environ={})
    assert resolve_flow_path(settings, "hello").name == "hello.yaml"
    assert resolve_flow_path(settings, "nested/deep").name == "deep.yaml"
    with pytest.raises(ConfigError):
        resolve_flow_path(settings, "missing")
