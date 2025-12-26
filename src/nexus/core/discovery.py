"""
Plugin discovery utilities.

Responsible for loading plugin packages configured in global/local settings
and registering callables decorated with ``@plugin``.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .config import load_global_configuration
from .types import PluginConfig, PluginSpec

logger = logging.getLogger(__name__)

# Global plugin registry -----------------------------------------------------

PLUGIN_REGISTRY: Dict[str, PluginSpec] = {}


def plugin(*, name: str, config: Optional[type[PluginConfig]] = None, description: Optional[str] = None, tags: Optional[List[str]] = None) -> Callable[[Callable], Callable]:
    """Decorator used by plugin authors to register their callable."""

    def decorator(func: Callable) -> Callable:
        if name in PLUGIN_REGISTRY:
            logger.debug("Plugin '%s' already registered; skipping duplicate", name)
            return func

        PLUGIN_REGISTRY[name] = PluginSpec(
            name=name,
            func=func,
            config_model=config,
            description=description or func.__doc__,
            tags=tags,
        )
        logger.debug("Registered plugin: %s", name)
        return func

    return decorator


# Discovery -----------------------------------------------------------------

def discover_from_path(path_str: str, project_root: Path) -> int:
    """Import a package (and sub-packages) to trigger plugin registration."""

    path = resolve_path(path_str, project_root)
    if not path.exists() or not path.is_dir():
        logger.warning("Package path not found: %s", path)
        return 0

    # Ensure the parent directory is discoverable by Python
    parent = path.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
        logger.debug("Added %s to sys.path", parent)
    package_name = path.name
    try:
        importlib.import_module(package_name)
        logger.debug("Successfully imported  configured plugin package '%s'", package_name)
    except Exception as exc:  # pylint: disable=broad-except
        import traceback
        logger.error(
            "Failed to import configured plugin package '%s': %s\n"
            "Error type: %s\n"
            "Package path: %s\n"
            "Traceback:\n%s",
            package_name,
            exc,
            type(exc).__name__,
            path,
            traceback.format_exc(),
        )
        return 0

    # If the main package was imported, now attempt to load the 'nexus' adapter module.
    adapter_module_name = f"{package_name}.nexus"
    try:
        importlib.import_module(adapter_module_name)
        logger.info("Successfully loaded 'nexus' adapter from package '%s'", package_name)
    except ImportError as exc:
        # Check if the ImportError is for the adapter module itself (meaning it doesn't exist)
        if exc.name == adapter_module_name:
            logger.debug("No 'nexus' adapter module found in package '%s'. This is acceptable.", package_name)
        else:
            # The adapter module exists, but one of its internal dependencies is missing.
            # This is a real error.
            import traceback
            logger.error(
                "Failed to load 'nexus' adapter from package '%s' due to missing dependency '%s': %s\n"
                "Error type: %s\n"
                "Adapter module: %s\n"
                "Traceback:\n%s",
                package_name,
                exc.name, # Log the name of the missing dependency
                exc,
                type(exc).__name__,
                adapter_module_name,
                traceback.format_exc(),
            )
            return 0 # Fail this discovery
    except Exception as exc: # Catch any other non-ImportError exceptions during adapter loading
        import traceback
        logger.error(
            "Failed to load 'nexus' adapter from package '%s' due to an unexpected error: %s\n"
            "Error type: %s\n"
            "Adapter module: %s\n"
            "Traceback:\n%s",
            package_name,
            exc,
            type(exc).__name__,
            adapter_module_name,
            traceback.format_exc(),
        )
        return 0 # Fail this discovery
    return 1


def resolve_path(path_str: str, project_root: Path) -> Path:
    expanded = Path(path_str).expanduser()
    if not expanded.is_absolute():
        expanded = project_root / expanded
    return expanded.resolve()


def discover_all_plugins(project_root: Path) -> None:
    clear_registry()
    global_config = load_global_configuration(project_root)

    packages: List[str] = list(dict.fromkeys(global_config.get("framework", {}).get("packages", [])))
    if not packages:
        logger.info("No discovery packages configured")
        return

    for package in packages:
        discover_from_path(package, project_root)

    logger.info("Discovery complete: %s plugins", len(PLUGIN_REGISTRY))


# Registry helpers -----------------------------------------------------------

def get_plugin(name: str) -> PluginSpec:
    if name not in PLUGIN_REGISTRY:
        raise KeyError(f"Plugin '{name}' not found")
    return PLUGIN_REGISTRY[name]


def list_plugins() -> Dict[str, PluginSpec]:
    return PLUGIN_REGISTRY.copy()


def clear_registry() -> None:
    PLUGIN_REGISTRY.clear()
