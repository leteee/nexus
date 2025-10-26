"""
Plugin discovery utilities.

Responsible for loading plugin packages configured in global/local settings
and registering callables decorated with ``@plugin``.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .config import load_global_configuration
from .types import PluginConfig, PluginSpec

logger = logging.getLogger(__name__)

# Global plugin registry -----------------------------------------------------

PLUGIN_REGISTRY: Dict[str, PluginSpec] = {}


def plugin(*, name: str, config: Optional[type[PluginConfig]] = None, description: str = None):
    """Decorator used by plugin authors to register their callable."""

    def decorator(func):
        if name in PLUGIN_REGISTRY:
            logger.debug("Plugin '%s' already registered; skipping duplicate", name)
            return func

        PLUGIN_REGISTRY[name] = PluginSpec(
            name=name,
            func=func,
            config_model=config,
            description=description or func.__doc__,
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
        importlib.import_module(package_name)  # 先加载主包
        adapter_module = f"{package_name}.nexus"
        if importlib.util.find_spec(adapter_module):
            importlib.import_module(adapter_module)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to import '%s': %s", package_name, exc)
        return 0

    logger.info("Imported package '%s'", package_name)
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
