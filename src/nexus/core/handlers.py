"""
Core handler registry for data I/O operations.

Handlers are registered via @handler decorator and manage
serialization/deserialization of different file formats.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Type

import pandas as pd

from .types import DataHandler

logger = logging.getLogger(__name__)

# Global handler registry
HANDLER_REGISTRY: Dict[str, Type[DataHandler]] = {}


def handler(handler_type: str):
    """
    Register a data handler class.

    Args:
        handler_type: Type identifier (e.g., 'csv', 'json')

    Example:
        @handler("csv")
        class CSVHandler:
            @property
            def produced_type(self) -> type:
                return pd.DataFrame

            def load(self, path: Path) -> pd.DataFrame:
                return pd.read_csv(path)

            def save(self, data: pd.DataFrame, path: Path) -> None:
                data.to_csv(path, index=False)
    """
    def decorator(cls):
        register_handler(handler_type, cls)
        return cls
    return decorator


def register_handler(handler_type: str, handler_class: Type[DataHandler]) -> None:
    """
    Register a data handler.

    Args:
        handler_type: Type identifier (e.g., 'csv', 'json')
        handler_class: Handler class implementing DataHandler protocol
    """
    HANDLER_REGISTRY[handler_type] = handler_class
    logger.debug(f"Registered handler: {handler_type}")


def get_handler(handler_type: str) -> DataHandler:
    """
    Get handler instance by type.

    Args:
        handler_type: Handler type (e.g., 'csv', 'json')

    Returns:
        Handler instance

    Raises:
        ValueError: If handler not registered
    """
    if handler_type not in HANDLER_REGISTRY:
        available = ', '.join(sorted(HANDLER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown handler: '{handler_type}'. Available: {available}"
        )

    return HANDLER_REGISTRY[handler_type]()


def get_handler_for_path(path: Path) -> DataHandler:
    """
    Get handler based on file extension.

    Args:
        path: File path

    Returns:
        Handler instance

    Raises:
        ValueError: If no handler for extension
    """
    suffix = path.suffix.lstrip(".")

    # Try direct match
    if suffix in HANDLER_REGISTRY:
        return get_handler(suffix)

    # Try aliases
    if suffix == "pkl":
        return get_handler("pickle")

    available = ', '.join(sorted(HANDLER_REGISTRY.keys()))
    raise ValueError(
        f"No handler for extension '.{suffix}'. Available: {available}"
    )


def preflight_type_check(
    data_source_name: str, expected_type: type, handler: DataHandler
) -> bool:
    """
    Check type compatibility between handler and expected type.

    Args:
        data_source_name: Data source name (for logging)
        expected_type: Expected type
        handler: Handler instance

    Returns:
        True if compatible
    """
    produced_type = handler.produced_type

    # Direct match
    if expected_type == produced_type:
        return True

    # DataFrame compatibility
    if expected_type == pd.DataFrame and produced_type == pd.DataFrame:
        return True

    # Object compatibility (pickle)
    if produced_type == object:
        logger.debug(f"Dynamic type for '{data_source_name}'")
        return True

    logger.warning(
        f"Type mismatch for '{data_source_name}': "
        f"expected {expected_type.__name__}, got {produced_type.__name__}"
    )
    return False
