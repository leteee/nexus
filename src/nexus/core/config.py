"""
Functional configuration management for the Nexus framework.

Following data_replay's pure functional approach to configuration.
All functions are pure with no side effects, enabling easy testing and caching.
"""

import json
import logging
import os
import yaml
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .types import PluginSpec, DataSource

logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _load_yaml_cached(file_path_str: str) -> Dict[str, Any]:
    """
    Cached YAML loader for performance.

    Args:
        file_path_str: String path for caching compatibility

    Returns:
        Loaded YAML content or empty dict if file doesn't exist
    """
    file_path = Path(file_path_str)
    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load YAML file {file_path}: {e}")
        return {}


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load YAML file safely with caching.

    Args:
        file_path: Path to YAML file

    Returns:
        Loaded content as dictionary
    """
    return _load_yaml_cached(str(file_path))


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge dictionaries with override precedence.

    Args:
        base: Base dictionary
        override: Override dictionary (higher priority)

    Returns:
        Merged dictionary
    """
    result = deepcopy(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and key in result
            and isinstance(result[key], dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_environment_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.

    Returns:
        Dictionary with environment-based configuration
    """
    env_config = {}
    env_mappings = {
        "NEXUS_LOG_LEVEL": "log_level",
        "NEXUS_CASES_ROOT": "cases_root",
        "NEXUS_PLUGIN_PATHS": "plugin_paths",
        "NEXUS_HANDLER_PATHS": "handler_paths",
    }

    for env_var, config_key in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            if config_key in ["plugin_paths", "handler_paths"]:
                env_config[config_key] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]
            else:
                env_config[config_key] = value

    if env_config:
        logger.debug(f"Loaded environment configuration: {env_config}")
    return env_config


def extract_plugin_defaults(plugin_registry: Dict[str, PluginSpec]) -> Dict[str, Dict]:
    """
    Extract default values from plugin configuration models.

    Args:
        plugin_registry: Registry of plugin specifications

    Returns:
        Mapping of plugin names to their default configurations
    """
    defaults_map = {}

    for name, spec in plugin_registry.items():
        if not spec.config_model or not issubclass(spec.config_model, BaseModel):
            defaults_map[name] = {}
            continue

        model_defaults = {}
        for field_name, field_info in spec.config_model.model_fields.items():
            # Skip DataSource fields - they're injected at runtime
            has_data_source = any(
                isinstance(item, DataSource) for item in field_info.metadata
            )
            if not has_data_source and field_info.default is not ...:
                model_defaults[field_name] = field_info.default

        defaults_map[name] = model_defaults

    logger.debug(f"Extracted defaults for {len(defaults_map)} plugins")
    return defaults_map


def resolve_data_source_paths(
    sources: Dict[str, Any], case_path: Path, project_root: Path
) -> Dict[str, Any]:
    """
    Resolve relative paths in data source configurations.

    Args:
        sources: Data source configurations
        case_path: Case directory path
        project_root: Project root path

    Returns:
        Data sources with resolved absolute paths
    """
    resolved_sources = deepcopy(sources)

    for source_name, config in resolved_sources.items():
        if "path" not in config or not isinstance(config["path"], str):
            continue

        # Support project_root template variable
        path_str = config["path"].format(project_root=project_root)
        path_obj = Path(path_str)

        # Resolve relative paths against case directory
        if not path_obj.is_absolute():
            path_obj = case_path / path_obj

        config["path"] = path_obj.resolve()

    return resolved_sources


def merge_data_sources(
    discovered: Dict[str, Any],
    global_config: Dict[str, Any],
    case_config: Dict[str, Any],
    case_path: Path,
    project_root: Path,
) -> Dict[str, Any]:
    """
    Merge data sources from all configuration layers.

    Priority: Case > Global > Discovered

    Args:
        discovered: Auto-discovered data sources
        global_config: Global configuration
        case_config: Case-specific configuration
        case_path: Case directory path
        project_root: Project root path

    Returns:
        Final merged data sources with resolved paths
    """
    # Merge configurations by priority
    merged = deepcopy(discovered)
    merged = deep_merge(merged, global_config.get("data_sources", {}))
    merged = deep_merge(merged, case_config.get("data_sources", {}))

    # Resolve all paths
    return resolve_data_source_paths(merged, case_path, project_root)


def get_plugin_configuration(
    plugin_name: str,
    plugin_spec: PluginSpec,
    case_config: Dict[str, Any],
    global_config: Dict[str, Any],
    plugin_defaults: Dict[str, Dict],
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate final plugin configuration following priority hierarchy.

    Priority: CLI > Case > Global > Plugin Defaults

    Args:
        plugin_name: Name of the plugin
        plugin_spec: Plugin specification
        case_config: Case configuration
        global_config: Global configuration
        plugin_defaults: Plugin default values
        cli_overrides: CLI argument overrides

    Returns:
        Final plugin configuration
    """
    cli_overrides = cli_overrides or {}

    if not plugin_spec.config_model or not issubclass(plugin_spec.config_model, BaseModel):
        return {}

    # Start with plugin defaults
    config = deepcopy(plugin_defaults.get(plugin_name, {}))

    # Apply global plugin configuration
    global_plugin_config = global_config.get("plugins", {}).get(plugin_name, {})
    config = deep_merge(config, global_plugin_config)

    # Apply case plugin configuration
    case_plugin_config = case_config.get("plugins", {}).get(plugin_name, {})
    config = deep_merge(config, case_plugin_config)

    # Apply CLI overrides (highest priority)
    config = deep_merge(config, cli_overrides)

    # Filter to only include fields defined in the plugin's config model
    final_config = {}
    for field_name, field_info in plugin_spec.config_model.model_fields.items():
        # Skip DataSource fields - they're injected separately
        has_data_source = any(
            isinstance(item, DataSource) for item in field_info.metadata
        )
        if has_data_source:
            continue

        # Include field if present in merged config or has default
        if field_name in config:
            final_config[field_name] = config[field_name]
        elif field_info.default is not ...:
            final_config[field_name] = field_info.default

    return final_config


@lru_cache(maxsize=128)
def create_configuration_context(
    project_root_str: str,
    case_path_str: str,
    plugin_registry_hash: str,
    discovered_sources_hash: str,
    cli_args_hash: str,
) -> Dict[str, Any]:
    """
    Create cached configuration context.

    Args:
        project_root_str: Project root path as string
        case_path_str: Case path as string
        plugin_registry_hash: Hash of plugin registry
        discovered_sources_hash: Hash of discovered sources
        cli_args_hash: Hash of CLI arguments

    Returns:
        Complete configuration context
    """
    # Reconstruct objects from hashed strings
    project_root = Path(project_root_str)
    case_path = Path(case_path_str)
    cli_args = json.loads(cli_args_hash) if cli_args_hash else {}
    discovered_sources = json.loads(discovered_sources_hash) if discovered_sources_hash else {}

    # Load configuration files
    global_config_path = project_root / "config" / "global.yaml"
    case_config_path = case_path / "case.yaml"

    global_config = load_yaml(global_config_path)
    case_config = load_yaml(case_config_path)
    env_config = load_environment_config()

    # Merge configurations (env overrides global, case overrides env)
    merged_global = deep_merge(global_config, env_config)
    final_case_config = deep_merge(merged_global, case_config)

    return {
        "project_root": project_root,
        "case_path": case_path,
        "global_config": merged_global,
        "case_config": final_case_config,
        "cli_args": cli_args,
        "discovered_sources": discovered_sources,
    }