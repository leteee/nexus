"""Engine configuration loading and layering.

Configuration precedence (lowest to highest):

1. built-in defaults from :class:`EngineSettings`
2. ``<project>/config/nexus.yaml``
3. ``<project>/config/nexus.local.yaml``
4. an optional extra config file (``NEXUS_CONFIG`` or ``--config-file``)
5. ``NEXUS__*`` environment variables (``__`` separates nested keys)
6. programmatic/CLI overrides

Flow-level ``vars`` and ``config`` are resolved later by the engine and are not
part of engine settings.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator

from .errors import ConfigError
from .models import ExecutionSettings, NexusModel
from .utils import deep_merge

ENV_PREFIX = "NEXUS__"
DEFAULT_CONFIG_FILES = ("config/nexus.yaml", "config/nexus.local.yaml")
PROJECT_MARKERS = ("pyproject.toml", "config/nexus.yaml", ".git")


class LoggingSettings(NexusModel):
    level: str = Field(default="INFO", description="Root log level for Nexus loggers.")
    file: str | None = Field(default=None, description="Optional log file, relative to the project root.")
    rich: bool = Field(default=True, description="Use rich-formatted console logging when available.")


class EngineSettings(NexusModel):
    """Resolved engine configuration."""

    version: str | int = Field(default=2, description="Settings schema version.")
    project_root: Path = Field(default_factory=Path.cwd, description="Project root used for discovery.")
    workdir: Path | None = Field(default=None, description="Default working directory for runs.")
    flow_paths: list[str] = Field(
        default_factory=lambda: ["flows"],
        description="Directories searched when a flow is referenced by name.",
    )
    node_modules: list[str] = Field(
        default_factory=list,
        description="Additional Python modules imported to register nodes.",
    )
    load_entry_points: bool = Field(default=True, description="Load node packs from 'nexus.nodes' entry points.")
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    max_subflow_depth: int = Field(default=8, ge=1, le=64)

    @field_validator("project_root", mode="before")
    @classmethod
    def _absolute_root(cls, value: Any) -> Any:
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else path

    def scope(self) -> dict[str, Any]:
        """Return the settings as a JSON-ish mapping for expressions."""

        return self.model_dump(mode="json")


def detect_project_root(start: Path | None = None) -> Path:
    """Find the nearest directory containing a project marker."""

    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    return current


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config file {path} must contain a mapping at the top level")
    return data


def _env_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key, raw in environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        path = key[len(ENV_PREFIX) :].lower().split("__")
        if not all(path):
            continue
        try:
            value = _plain_value(yaml.safe_load(raw))
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid value for environment variable {key}: {exc}") from exc
        cursor = overrides
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
            if not isinstance(cursor, dict):
                raise ConfigError(f"environment variable {key} conflicts with another override")
        cursor[path[-1]] = value
    return overrides


def _coerce_root_paths(layer: dict[str, Any], root: Path) -> dict[str, Any]:
    """Resolve path-valued settings against the project root."""

    result = dict(layer)
    if "project_root" in result and result["project_root"] is not None:
        project = Path(result["project_root"]).expanduser()
        result["project_root"] = str(project if project.is_absolute() else (root / project))
    if "workdir" in result and result["workdir"] is not None:
        workdir = Path(result["workdir"]).expanduser()
        result["workdir"] = str(workdir if workdir.is_absolute() else (root / workdir))
    return result


def load_settings(
    project_root: Path | str | None = None,
    *,
    config_files: list[Path | str] | None = None,
    overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> EngineSettings:
    """Load merged :class:`EngineSettings` for *project_root*."""

    root = Path(project_root).expanduser().resolve() if project_root else detect_project_root()
    environ = os.environ if environ is None else environ
    merged: dict[str, Any] = {}

    for relative in DEFAULT_CONFIG_FILES:
        path = root / relative
        if path.exists():
            merged = deep_merge(merged, _read_yaml(path))

    extra_files: list[Path] = [Path(item).expanduser() for item in (config_files or [])]
    env_config = environ.get("NEXUS_CONFIG")
    if env_config and not extra_files:
        extra_files.append(Path(env_config).expanduser())
    for path in extra_files:
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            raise ConfigError(f"config file not found: {path}")
        merged = deep_merge(merged, _read_yaml(path))

    merged = deep_merge(merged, _env_overrides(environ))
    if overrides:
        merged = deep_merge(merged, dict(overrides))

    merged = _coerce_root_paths(merged, root)
    merged.setdefault("project_root", str(root))
    try:
        return EngineSettings.model_validate(merged)
    except Exception as exc:
        raise ConfigError(f"invalid engine configuration: {exc}") from exc


def _plain_value(value: Any) -> Any:
    """Keep CLI overrides JSON/YAML friendly (PyYAML parses timestamps)."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    return value


def parse_cli_set(items: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Parse ``key.path=value`` CLI overrides into a nested mapping."""

    result: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ConfigError(f"invalid override '{item}'; expected key=value")
        key, raw = item.split("=", 1)
        if not key:
            raise ConfigError(f"invalid override '{item}'; empty key")
        try:
            value = _plain_value(yaml.safe_load(raw))
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid value for '{key}': {exc}") from exc
        cursor = result
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
            if not isinstance(cursor, dict):
                raise ConfigError(f"override '{key}' conflicts with another override")
        cursor[parts[-1]] = value
    return result


def resolve_flow_path(settings: EngineSettings, reference: str | Path) -> Path:
    """Resolve a flow path or a bare flow name from configured search paths."""

    candidate = Path(reference).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    if candidate.suffix in {".yaml", ".yml"} and not candidate.is_absolute():
        local = (Path.cwd() / candidate).resolve()
        if local.is_file():
            return local

    relative = candidate
    if relative.is_absolute():
        try:
            relative = relative.relative_to(settings.project_root)
        except ValueError:
            relative = Path(relative.name)
    names = (
        [relative]
        if relative.suffix
        else [relative.with_suffix(".yaml"), relative.with_suffix(".yml")]
    )

    searched: list[Path] = []
    for root_name in settings.flow_paths:
        root = Path(os.path.expandvars(os.path.expanduser(root_name)))
        if not root.is_absolute():
            root = settings.project_root / root
        if not root.exists():
            continue
        searched.append(root)
        for name in names:
            direct = root / name
            if direct.is_file():
                return direct.resolve()
            for match in sorted(root.rglob(str(name))):
                if match.is_file():
                    return match.resolve()

    available: list[str] = []
    for root in searched:
        for path in sorted(root.rglob("*.y*ml")):
            try:
                available.append(str(path.relative_to(root)))
            except ValueError:
                continue
    suffix = f" Available flows: {', '.join(available[:20])}" if available else ""
    raise ConfigError(f"flow '{reference}' not found in {', '.join(str(path) for path in searched) or 'search paths'}.{suffix}")
