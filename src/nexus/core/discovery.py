"""
Plugin and handler discovery system.

Discovers extensions by importing Python packages configured in global.yaml.
Extensions register themselves via @plugin and @handler decorators.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Dict, List, get_type_hints

from .types import DataSink, DataSource, PluginSpec

logger = logging.getLogger(__name__)

# Global plugin registry
PLUGIN_REGISTRY: Dict[str, PluginSpec] = {}


def plugin(
    *,
    name: str,
    config: type = None,
    description: str = None,
):
    """
    Decorator to register a function as a plugin.

    Args:
        name: Unique name for the plugin
        config: Pydantic model class for plugin configuration
        description: Plugin description (uses docstring if not provided)

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


def discover_io_declarations(
    plugin_spec: PluginSpec,
) -> tuple[Dict[str, DataSource], Dict[str, DataSink]]:
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


def discover_from_path(path_str: str, project_root: Path) -> tuple[int, int]:
    """
    Import a Python package from path.

    Convention: directory name = package name
    Parent directory is added to sys.path, then package is imported.

    Args:
        path_str: Path to package (e.g., "nexus_workspace/alpha")
        project_root: Project root directory

    Returns:
        (plugins_count, handlers_count)

    Example:
        "nexus_workspace/alpha" → sys.path += ["nexus_workspace"], import alpha
    """
    from .handlers import HANDLER_REGISTRY

    initial_plugin_count = len(PLUGIN_REGISTRY)
    initial_handler_count = len(HANDLER_REGISTRY)

    # Resolve path
    path = resolve_path(path_str, project_root)

    if not path.exists() or not path.is_dir():
        logger.error(f"Package path not found: {path}")
        return 0, 0

    # Verify it's a Python package
    if not (path / "__init__.py").exists():
        logger.warning(f"Not a Python package (missing __init__.py): {path}")
        return 0, 0

    # Extract package name and parent path
    package_name = path.name
    parent_path = str(path.parent.resolve())

    # Add to sys.path
    if parent_path not in sys.path:
        sys.path.insert(0, parent_path)
        logger.debug(f"Added to sys.path: {parent_path}")

    # Import package
    try:
        importlib.import_module(package_name)
        logger.debug(f"Imported package: {package_name}")
    except ImportError as e:
        logger.error(f"Failed to import '{package_name}': {e}")
        return 0, 0
    except Exception as e:
        logger.error(f"Error loading '{package_name}': {e}")
        return 0, 0

    # Count discoveries
    plugins_found = len(PLUGIN_REGISTRY) - initial_plugin_count
    handlers_found = len(HANDLER_REGISTRY) - initial_handler_count

    if plugins_found > 0 or handlers_found > 0:
        logger.info(
            f"Package '{package_name}': "
            f"{plugins_found} plugin(s), {handlers_found} handler(s)"
        )

    return plugins_found, handlers_found


def resolve_path(path_str: str, project_root: Path) -> Path:
    """
    Resolve path string to absolute Path.

    Supports:
    - Relative paths (resolved from project root)
    - Absolute paths
    - Home directory (~)
    - Environment variables
    """
    import os

    # Expand environment variables and home directory
    expanded = os.path.expanduser(os.path.expandvars(path_str))
    path = Path(expanded)

    # Make relative paths absolute
    if not path.is_absolute():
        path = project_root / path

    return path.resolve()


def discover_all_plugins_and_handlers(project_root: Path) -> None:
    """
    Import packages from config/global.yaml and config/local.yaml.

    Configuration files (in precedence order):
    1. config/global.yaml - Project defaults (version controlled)
    2. config/local.yaml - User overrides (gitignored, optional)

    The local.yaml is deep-merged into global.yaml, supporting all config sections.

    Args:
        project_root: Project root containing config/ directory
    """
    from .config import deep_merge, load_yaml
    from .handlers import HANDLER_REGISTRY

    # Load global configuration
    try:
        global_config = load_yaml(project_root / "config" / "global.yaml")
    except FileNotFoundError:
        logger.warning("Global config not found, skipping discovery")
        return
    except Exception as e:
        logger.error(f"Failed to load global config: {e}")
        return

    # Merge local configuration if exists
    local_config_path = project_root / "config" / "local.yaml"
    if local_config_path.exists():
        try:
            local_config = load_yaml(local_config_path)
            if local_config:
                global_config = deep_merge(global_config, local_config)
                logger.info("Merged local.yaml configuration")
        except Exception as e:
            logger.warning(f"Failed to load local config: {e}")

    # Extract packages for discovery
    packages = global_config.get("framework", {}).get("packages", [])

    # Remove duplicates (keep last occurrence)
    packages = list(dict.fromkeys(packages))

    if not packages:
        logger.warning("No packages configured in framework.packages")
        return

    logger.info(f"Importing {len(packages)} package(s)")

    # Import each package
    total_plugins = 0
    total_handlers = 0

    for path_str in packages:
        plugins, handlers = discover_from_path(path_str, project_root)
        total_plugins += plugins
        total_handlers += handlers

    # Summary
    logger.info(
        f"Discovery complete: {len(PLUGIN_REGISTRY)} plugins, "
        f"{len(HANDLER_REGISTRY)} handlers"
    )


def get_plugin(name: str) -> PluginSpec:
    """Get plugin by name."""
    if name not in PLUGIN_REGISTRY:
        raise KeyError(f"Plugin '{name}' not found")
    return PLUGIN_REGISTRY[name]


def list_plugins() -> Dict[str, PluginSpec]:
    """Get all registered plugins."""
    return PLUGIN_REGISTRY.copy()


def clear_registry() -> None:
    """Clear plugin registry (for testing)."""
    PLUGIN_REGISTRY.clear()

