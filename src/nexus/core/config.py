"""
Configuration management for Nexus framework (business config only).

Precedence (business): plugin defaults < case/template < CLI overrides.
System settings are handled separately via setting*.yaml.
Typical usage:
    case_cfg = load_yaml(Path("cases/demo/case.yaml"))
    cli = {"plugins": {"MyPlugin": {"foo": 1}}}
    ctx = create_configuration_context(case_cfg, cli, PLUGIN_REGISTRY)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

from .config_processors import ProcessingContext, process_plugin_config

logger = logging.getLogger(__name__)

SYSTEM_CONFIG_FILES = ("setting.yaml", "setting-local.yaml")
SYSTEM_ALLOWED_TOP_LEVEL = {"framework", "logging"}


# YAML loading ----------------------------------------------------------------


@lru_cache(maxsize=128)
def _load_yaml_cached(file_path_str: str) -> Dict[str, Any]:
    try:
        with open(file_path_str, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path_str}: {e}")


def load_yaml(file_path: Path) -> Dict[str, Any]:
    return _load_yaml_cached(str(file_path))


# System config ---------------------------------------------------------------


def _iter_config_layers(project_root: Path, file_names: tuple[str, ...]):
    config_dir = project_root / "config"
    for file_name in file_names:
        path = config_dir / file_name
        if not path.exists():
            continue
        layer = load_yaml(path)
        if layer:
            yield layer


def _filter_system_config(config: Dict[str, Any]) -> Dict[str, Any]:
    filtered = {k: v for k, v in config.items() if k in SYSTEM_ALLOWED_TOP_LEVEL}
    return filtered


def load_system_configuration(project_root: Path, cli_overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for layer in _iter_config_layers(project_root, SYSTEM_CONFIG_FILES):
        merged = deep_merge(merged, layer)
    merged = _filter_system_config(merged)
    if cli_overrides:
        merged = deep_merge(merged, _filter_system_config(cli_overrides))
    return merged


# Deep merge ------------------------------------------------------------------


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# Plugin defaults -------------------------------------------------------------


def extract_plugin_defaults(plugin_registry: Dict[str, Any]) -> Dict[str, Dict]:
    defaults_map = {}
    for name, spec in plugin_registry.items():
        try:
            if hasattr(spec, "config_model") and spec.config_model:
                model_instance = spec.config_model()
                defaults_map[name] = model_instance.model_dump()
            else:
                defaults_map[name] = {}
        except Exception:
            defaults_map[name] = {}
    return defaults_map


# Business configuration ------------------------------------------------------


def create_configuration_context(
    case_config: Dict[str, Any],
    cli_overrides: Dict[str, Any],
    plugin_registry: Dict[str, Any],
) -> Dict[str, Any]:
    """Business configuration precedence: plugin defaults < case/template < CLI."""
    context: Dict[str, Any] = {"plugins": extract_plugin_defaults(plugin_registry)}
    context = deep_merge(context, case_config)
    context = deep_merge(context, cli_overrides)
    return context


def get_plugin_configuration(
    plugin_name: str,
    config_context: Dict[str, Any],
    step_config: Dict[str, Any],
    config_model: type | None = None,
    proc_ctx: ProcessingContext | None = None,
    defaults: Dict[str, Any] | None = None,
) -> Any:
    # Defaults from model
    plugin_defaults = {}
    if config_model:
        try:
            plugin_defaults = config_model().model_dump()
        except Exception:
            plugin_defaults = {}

    global_plugin_config = config_context.get("plugins", {}).get(plugin_name, {})
    merged_config = deep_merge(plugin_defaults, global_plugin_config)
    merged_config = deep_merge(merged_config, step_config)

    if proc_ctx:
        merged_config = process_plugin_config(merged_config, defaults or {}, None, proc_ctx)

    if config_model:
        return config_model(**merged_config)
    return merged_config
