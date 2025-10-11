"""
Plugin discovery and registration system.

Following data_replay's automatic discovery pattern with functional approach.
Discovers plugins from various sources and builds the plugin registry.
"""

import importlib
import inspect
import logging
import os
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


def discover_plugins_from_module(
    module_name: str, search_paths: List[str] = None
) -> int:
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
        if discovered_count > 0:
            logger.debug(f"  Found: {module_name} ({discovered_count} plugins)")
        return discovered_count

    except ImportError as e:
        logger.warning(f"  Failed to import '{module_name}': {e}")
        return 0
    except Exception as e:
        logger.error(f"  Error in '{module_name}': {e}")
        return 0


def resolve_path(path_str: str, project_root: Path) -> Path:
    """
    Resolve a path string to an absolute Path object.

    Supports:
    - Relative paths (resolved relative to project root)
    - Absolute paths
    - Home directory paths (~)
    - Environment variable expansion

    Args:
        path_str: Path string to resolve
        project_root: Project root directory for resolving relative paths

    Returns:
        Resolved absolute Path object
    """
    # Expand environment variables
    expanded_path = os.path.expandvars(path_str)

    # Expand user home directory
    expanded_path = os.path.expanduser(expanded_path)

    path_obj = Path(expanded_path)

    # If it's not absolute, make it relative to project root
    if not path_obj.is_absolute():
        path_obj = project_root / path_obj

    return path_obj.resolve()


def discover_plugins_from_paths(
    paths: List[str], project_root: Path, recursive: bool = True
) -> int:
    """
    Discover plugins from multiple directory paths.

    Args:
        paths: List of directory paths to scan
        project_root: Project root directory
        recursive: Whether to search recursively

    Returns:
        Total number of plugins discovered
    """
    logger.info(f"Plugin discovery: scanning {len(paths)} path(s)")
    total_discovered = 0

    for path_str in paths:
        try:
            resolved_path = resolve_path(path_str, project_root)

            if resolved_path.exists() and resolved_path.is_dir():
                count = discover_plugins_from_directory(resolved_path, recursive)
                total_discovered += count
                if count > 0:
                    logger.debug(f"  └─ {resolved_path.name}: {count} plugin(s)")
            else:
                logger.warning(
                    f"  └─ Plugin path does not exist: {resolved_path}"
                )

        except Exception as e:
            logger.error(f"  └─ Error processing '{path_str}': {e}")

    if total_discovered > 0:
        logger.info(f"Plugin discovery: {total_discovered} plugin(s) from {len(paths)} path(s)")
    return total_discovered


def discover_handlers_from_paths(
    paths: List[str], project_root: Path, recursive: bool = True
) -> int:
    """
    Discover handlers from multiple directory paths.

    Args:
        paths: List of directory paths to scan
        project_root: Project root directory
        recursive: Whether to search recursively

    Returns:
        Total number of handlers discovered
    """
    logger.info(f"Handler discovery: scanning {len(paths)} path(s)")
    total_discovered = 0

    for path_str in paths:
        try:
            resolved_path = resolve_path(path_str, project_root)

            if resolved_path.exists() and resolved_path.is_dir():
                count = discover_handlers_from_directory(resolved_path, recursive)
                total_discovered += count
                if count > 0:
                    logger.debug(f"  └─ {resolved_path.name}: {count} handler(s)")
            else:
                logger.warning(
                    f"  └─ Handler path does not exist: {resolved_path}"
                )

        except Exception as e:
            logger.error(f"  └─ Error processing '{path_str}': {e}")

    if total_discovered > 0:
        logger.info(f"Handler discovery: {total_discovered} handler(s) from {len(paths)} path(s)")
    return total_discovered


def discover_handlers_from_directory(directory: Path, recursive: bool = True) -> int:
    """
    Discover handlers from all Python files in a directory.

    Args:
        directory: Directory to search for handler files
        recursive: Whether to search recursively

    Returns:
        Number of handlers discovered
    """
    if not directory.exists() or not directory.is_dir():
        logger.warning(f"Handler directory not found: {directory}")
        return 0

    from .handlers import HANDLER_REGISTRY

    initial_count = len(HANDLER_REGISTRY)

    # Get Python files
    if recursive:
        python_files = list(directory.glob("**/*.py"))
    else:
        python_files = list(directory.glob("*.py"))

    logger.debug(f"  Scanning: {directory}")

    for py_file in python_files:
        if py_file.name.startswith("__"):
            continue

        try:
            # Convert file path to module name
            relative_path = py_file.relative_to(directory.parent)
            module_parts = relative_path.with_suffix("").parts
            module_name = ".".join(module_parts)

            # Import the module to register handlers
            discover_handlers_from_module(
                module_name, search_paths=[str(directory.parent)]
            )

        except Exception as e:
            logger.warning(f"  Could not load {py_file.name}: {e}")

    discovered_count = len(HANDLER_REGISTRY) - initial_count
    return discovered_count


def discover_handlers_from_module(
    module_name: str, search_paths: List[str] = None
) -> int:
    """
    Discover and register handlers from a Python module.

    Args:
        module_name: Name of the module to import
        search_paths: Additional paths to search for the module

    Returns:
        Number of handlers discovered
    """
    if search_paths:
        import sys

        for path in search_paths:
            if path not in sys.path:
                sys.path.insert(0, str(path))

    try:
        from .handlers import HANDLER_REGISTRY, register_handler

        initial_count = len(HANDLER_REGISTRY)

        module = importlib.import_module(module_name)

        # Look for handler classes in the module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if it looks like a handler (has load and save methods)
            if (
                hasattr(obj, "load")
                and hasattr(obj, "save")
                and hasattr(obj, "produced_type")
            ):

                # Try to register the handler
                # Use the class name without 'Handler' suffix as the type
                handler_type = name.lower().replace("handler", "")
                if handler_type:
                    try:
                        register_handler(handler_type, obj)
                    except Exception as e:
                        logger.debug(f"Could not register handler {name}: {e}")

        discovered_count = len(HANDLER_REGISTRY) - initial_count
        if discovered_count > 0:
            logger.debug(f"  Found: {module_name} ({discovered_count} handlers)")
        return discovered_count

    except ImportError as e:
        logger.warning(f"  Failed to import '{module_name}': {e}")
        return 0
    except Exception as e:
        logger.error(f"  Error in '{module_name}': {e}")
        return 0


def discover_plugins_from_directory(directory: Path, recursive: bool = True) -> int:
    """
    Discover plugins from all Python files in a directory.

    Args:
        directory: Directory to search for plugin files
        recursive: Whether to search recursively

    Returns:
        Number of plugins discovered
    """
    if not directory.exists() or not directory.is_dir():
        logger.warning(f"Plugin directory not found: {directory}")
        return 0

    discovered_count = 0

    # Get Python files
    if recursive:
        python_files = list(directory.glob("**/*.py"))
    else:
        python_files = list(directory.glob("*.py"))

    logger.debug(f"  Scanning: {directory}")

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
            logger.warning(f"  Could not load {py_file.name}: {e}")

    return discovered_count


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


def discover_all_plugins_and_handlers(project_root: Path) -> None:
    """
    Unified plugin and handler discovery from global configuration.

    This function is the single source of truth for plugin/handler discovery logic.
    Used by both PipelineEngine and CLI to ensure consistent discovery behavior.

    Args:
        project_root: Project root directory containing config/global.yaml

    Side Effects:
        - Populates PLUGIN_REGISTRY with discovered plugins
        - Populates HANDLER_REGISTRY with discovered handlers
        - Logs discovery progress and results

    Discovery Process:
        1. Load global configuration from config/global.yaml
        2. Discover plugins from paths specified in discovery.plugins.paths
        3. Discover handlers from core directory + any configured handler paths

    Note:
        This function is idempotent - plugins/handlers are only registered once.
        Subsequent calls will see "Discovered 0" due to duplicate detection.
    """
    from .config import load_yaml

    # Load global configuration
    try:
        global_config = load_yaml(project_root / "config" / "global.yaml")
    except FileNotFoundError:
        logger.warning(f"Global config not found at {project_root / 'config' / 'global.yaml'}")
        return
    except Exception as e:
        logger.error(f"Error loading global config: {e}")
        return

    discovery_config = global_config.get("framework", {}).get("discovery", {})

    # Discover plugins from configured paths
    plugin_config = discovery_config.get("plugins", {})
    plugin_paths = plugin_config.get("paths", [])
    recursive = plugin_config.get("recursive", True)

    if plugin_paths:
        discover_plugins_from_paths(
            plugin_paths,
            project_root,
            recursive=recursive,
        )

    # Discover handlers from configured paths
    handler_config = discovery_config.get("handlers", {})
    handler_paths = handler_config.get("paths", [])

    if handler_paths:
        discover_handlers_from_paths(handler_paths, project_root)

    # Import HANDLER_REGISTRY for final summary
    from .handlers import HANDLER_REGISTRY

    logger.info(f"Registry ready: {len(PLUGIN_REGISTRY)} plugins, {len(HANDLER_REGISTRY)} handlers")
