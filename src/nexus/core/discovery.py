"""
Plugin discovery and registration system.

Following data_replay's automatic discovery pattern with functional approach.
Discovers plugins from various sources and builds the plugin registry.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import Dict, List, get_type_hints

from .types import PluginSpec, DataSource, DataSink

logger = logging.getLogger(__name__)

# Global plugin registry
PLUGIN_REGISTRY: Dict[str, PluginSpec] = {}


def plugin(
    *,
    name: str,
    config: type = None,
    description: str = None,
    output_key: str = None,
):
    """
    Decorator to register a function as a plugin.

    Args:
        name: Unique name for the plugin
        config: Pydantic model class for plugin configuration
        description: Plugin description (uses docstring if not provided)
        output_key: Key for storing plugin output in DataHub

    Returns:
        Decorated function
    """

    def decorator(func):
        # Create plugin specification
        spec = PluginSpec(
            name=name,
            func=func,
            config_model=config,
            description=description or func.__doc__,
            output_key=output_key,
        )

        # Check for duplicate registration
        if name in PLUGIN_REGISTRY:
            logger.debug(f"Plugin '{name}' already registered, skipping")
            return func

        # Register the plugin
        PLUGIN_REGISTRY[name] = spec
        logger.debug(f"Registered plugin: {name}")

        # Return original function
        return func

    return decorator


def discover_io_declarations(plugin_spec: PluginSpec) -> tuple[Dict[str, DataSource], Dict[str, DataSink]]:
    """
    Discover DataSource and DataSink declarations from a plugin's config model.

    Args:
        plugin_spec: Plugin specification

    Returns:
        Tuple of (data_sources, data_sinks) discovered from the plugin
    """
    data_sources = {}
    data_sinks = {}

    if not plugin_spec.config_model:
        return data_sources, data_sinks

    try:
        type_hints = get_type_hints(plugin_spec.config_model, include_extras=True)
    except (NameError, TypeError) as e:
        logger.warning(f"Could not resolve type hints for {plugin_spec.name}: {e}")
        return data_sources, data_sinks

    for field_name, field_type in type_hints.items():
        # Check for annotations in the field metadata
        if hasattr(field_type, "__metadata__"):
            for metadata in field_type.__metadata__:
                if isinstance(metadata, DataSource):
                    data_sources[metadata.name] = metadata
                elif isinstance(metadata, DataSink):
                    data_sinks[metadata.name] = metadata

    logger.debug(
        f"Plugin '{plugin_spec.name}' declares {len(data_sources)} sources, "
        f"{len(data_sinks)} sinks"
    )
    return data_sources, data_sinks


def discover_plugins_from_module(module_name: str, search_paths: List[str] = None) -> int:
    """
    Discover and register plugins from a Python module.

    Args:
        module_name: Name of the module to import
        search_paths: Additional paths to search for the module

    Returns:
        Number of plugins discovered
    """
    if search_paths:
        import sys
        for path in search_paths:
            if path not in sys.path:
                sys.path.insert(0, str(path))

    try:
        module = importlib.import_module(module_name)
        initial_count = len(PLUGIN_REGISTRY)

        # Force execution of the module to trigger plugin registration
        importlib.reload(module)

        discovered_count = len(PLUGIN_REGISTRY) - initial_count
        logger.info(f"Discovered {discovered_count} plugins from module '{module_name}'")
        return discovered_count

    except ImportError as e:
        logger.warning(f"Could not import plugin module '{module_name}': {e}")
        return 0
    except Exception as e:
        logger.error(f"Error discovering plugins from '{module_name}': {e}")
        return 0


def discover_plugins_from_directory(directory: Path) -> int:
    """
    Discover plugins from all Python files in a directory.

    Args:
        directory: Directory to search for plugin files

    Returns:
        Number of plugins discovered
    """
    if not directory.exists() or not directory.is_dir():
        logger.warning(f"Plugin directory not found: {directory}")
        return 0

    discovered_count = 0
    python_files = list(directory.glob("**/*.py"))

    for py_file in python_files:
        if py_file.name.startswith("__"):
            continue

        try:
            # Convert file path to module name
            relative_path = py_file.relative_to(directory.parent)
            module_parts = relative_path.with_suffix("").parts
            module_name = ".".join(module_parts)

            discovered_count += discover_plugins_from_module(
                module_name, search_paths=[str(directory.parent)]
            )

        except Exception as e:
            logger.warning(f"Could not load plugin file {py_file}: {e}")

    logger.info(f"Discovered {discovered_count} plugins from directory {directory}")
    return discovered_count


def auto_discover_data_sources(active_plugins: List[str]) -> Dict[str, Dict]:
    """
    Auto-discover data sources from active plugins.

    Args:
        active_plugins: List of plugin names to analyze

    Returns:
        Dictionary of discovered data source configurations
    """
    discovered_sources = {}

    for plugin_name in active_plugins:
        if plugin_name not in PLUGIN_REGISTRY:
            logger.warning(f"Plugin '{plugin_name}' not found in registry")
            continue

        plugin_spec = PLUGIN_REGISTRY[plugin_name]
        sources, sinks = discover_io_declarations(plugin_spec)

        # Add discovered sources to the registry
        for source_name, source_annotation in sources.items():
            if source_name not in discovered_sources:
                # Create a basic configuration for the discovered source
                discovered_sources[source_name] = {
                    "path": f"{source_name}.csv",  # Default path
                    "handler": "csv",  # Default handler
                    "must_exist": True,
                    **source_annotation.handler_args,
                }

        # Add discovered sinks as optional data sources
        for sink_name, sink_annotation in sinks.items():
            if sink_name not in discovered_sources:
                discovered_sources[sink_name] = {
                    "path": f"{sink_name}.csv",  # Default path
                    "handler": "csv",  # Default handler
                    "must_exist": False,  # Sinks are outputs, don't need to exist
                    **sink_annotation.handler_args,
                }

    logger.info(f"Auto-discovered {len(discovered_sources)} data sources")
    return discovered_sources


def get_plugin(name: str) -> PluginSpec:
    """
    Get a plugin by name.

    Args:
        name: Plugin name

    Returns:
        Plugin specification

    Raises:
        KeyError: If plugin not found
    """
    if name not in PLUGIN_REGISTRY:
        raise KeyError(f"Plugin '{name}' not found in registry")
    return PLUGIN_REGISTRY[name]


def list_plugins() -> Dict[str, PluginSpec]:
    """
    Get all registered plugins.

    Returns:
        Dictionary of all plugin specifications
    """
    return PLUGIN_REGISTRY.copy()


def clear_registry() -> None:
    """Clear the plugin registry (useful for testing)."""
    PLUGIN_REGISTRY.clear()
    logger.debug("Plugin registry cleared")