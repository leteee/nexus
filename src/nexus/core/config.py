"""
Simplified configuration management for Nexus framework.

Clean hierarchy: global → case → CLI overrides
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@lru_cache(maxsize=128)
def _load_yaml_cached(file_path_str: str) -> Dict[str, Any]:
    """Cached YAML loading to avoid repeated file reads."""
    try:
        with open(file_path_str, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path_str}: {e}")


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """Load YAML configuration file with caching."""
    return _load_yaml_cached(str(file_path))


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Override dictionary

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def create_configuration_context(
    global_config: Dict[str, Any],
    case_config: Dict[str, Any],
    cli_overrides: Dict[str, Any],
    plugin_registry: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create configuration context with proper hierarchy.

    Args:
        global_config: Global configuration
        case_config: Case configuration
        cli_overrides: CLI overrides
        plugin_registry: Plugin registry for defaults

    Returns:
        Merged configuration context
    """
    # Start with global config
    context = global_config.copy()

    # Merge case config
    context = deep_merge(context, case_config)

    # Apply CLI overrides
    context = deep_merge(context, cli_overrides)

    # Extract plugin defaults if not already present
    if "plugin_defaults" not in context:
        context["plugin_defaults"] = extract_plugin_defaults(plugin_registry)

    return context


def extract_plugin_defaults(plugin_registry: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Extract default values from plugin configuration models.

    Args:
        plugin_registry: Registry of available plugins

    Returns:
        Mapping of plugin names to their default configurations
    """
    defaults_map = {}

    for name, spec in plugin_registry.items():
        try:
            if hasattr(spec, "config_model") and spec.config_model:
                # Extract defaults from pydantic model
                model_instance = spec.config_model()
                defaults_map[name] = model_instance.model_dump()
            else:
                defaults_map[name] = {}
        except Exception:
            # If we can't extract defaults, use empty dict
            defaults_map[name] = {}

    return defaults_map


def get_plugin_configuration(
    plugin_name: str,
    config_context: Dict[str, Any],
    step_config: Dict[str, Any],
    config_model: Optional[type] = None,
) -> Any:
    """
    Get final plugin configuration by merging all sources.

    Args:
        plugin_name: Name of the plugin
        config_context: Global configuration context
        step_config: Step-specific configuration
        config_model: Plugin's configuration model class

    Returns:
        Plugin configuration instance
    """
    # Start with plugin defaults from global config
    plugin_defaults = config_context.get("plugin_defaults", {}).get(plugin_name, {})

    # Merge with global plugin config
    global_plugin_config = config_context.get("plugins", {}).get(plugin_name, {})
    merged_config = deep_merge(plugin_defaults, global_plugin_config)

    # Merge with step-specific config
    merged_config = deep_merge(merged_config, step_config)

    # Create model instance if available
    if config_model:
        return config_model(**merged_config)
    else:
        return merged_config
