"""
Core handler registry and utilities for Nexus framework.

This module provides the central handler registry and utility functions
for managing data handlers. Handler implementations can be defined in:
- Custom handler modules (handlers/ directory)
- Plugin-specific handlers
- Third-party handler packages
"""

import logging
from pathlib import Path
from typing import Any, Dict, Type

import pandas as pd

from .types import DataHandler

logger = logging.getLogger(__name__)


# Global handler registry mapping handler types to handler classes
HANDLER_REGISTRY: Dict[str, Type[DataHandler]] = {}


def register_handler(handler_type: str, handler_class: Type[DataHandler]) -> None:
    """
    Register a new data handler.

    Args:
        handler_type: Type identifier for the handler (e.g., 'csv', 'json')
        handler_class: Handler class implementing DataHandler protocol

    Example:
        >>> class MyHandler:
        ...     @property
        ...     def produced_type(self):
        ...         return dict
        ...     def load(self, path): ...
        ...     def save(self, data, path): ...
        >>> register_handler('myformat', MyHandler)
    """
    HANDLER_REGISTRY[handler_type] = handler_class
    logger.debug(f"    Registered: '{handler_type}' ({handler_class.__name__})")


def get_handler(handler_type: str) -> DataHandler:
    """
    Get handler instance by type.

    Args:
        handler_type: Type of handler (e.g., 'csv', 'json')

    Returns:
        Handler instance

    Raises:
        ValueError: If handler type is not registered

    Example:
        >>> handler = get_handler('csv')
        >>> df = handler.load(Path('data.csv'))
    """
    if handler_type not in HANDLER_REGISTRY:
        available = ', '.join(sorted(HANDLER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown handler type: '{handler_type}'. "
            f"Available handlers: {available}"
        )

    handler_class = HANDLER_REGISTRY[handler_type]
    return handler_class()


def get_handler_for_path(path: Path) -> DataHandler:
    """
    Get appropriate handler based on file extension.

    Args:
        path: File path

    Returns:
        Handler instance

    Raises:
        ValueError: If no handler found for file extension

    Example:
        >>> handler = get_handler_for_path(Path('data.csv'))
        >>> df = handler.load(Path('data.csv'))
    """
    suffix = path.suffix.lstrip(".")
    if suffix in HANDLER_REGISTRY:
        return get_handler(suffix)

    # Try common aliases
    if suffix in ["pkl"]:
        return get_handler("pickle")

    available = ', '.join(sorted(HANDLER_REGISTRY.keys()))
    raise ValueError(
        f"No handler found for file extension: '.{suffix}'. "
        f"Available handlers: {available}"
    )


def preflight_type_check(
    data_source_name: str, expected_type: type, handler: DataHandler
) -> bool:
    """
    Perform type compatibility check between handler and expected type.

    This is used during pipeline setup to verify that data sources
    will produce the expected types before actually loading data.

    Args:
        data_source_name: Name of data source for logging
        expected_type: Expected data type
        handler: Data handler instance

    Returns:
        True if types are compatible, False otherwise

    Example:
        >>> handler = get_handler('csv')
        >>> is_compatible = preflight_type_check('my_data', pd.DataFrame, handler)
    """
    produced_type = handler.produced_type

    # Direct type match
    if expected_type == produced_type:
        logger.debug(f"Type check passed for '{data_source_name}': {expected_type.__name__}")
        return True

    # DataFrame compatibility
    if expected_type == pd.DataFrame and produced_type == pd.DataFrame:
        logger.debug(f"DataFrame type check passed for '{data_source_name}'")
        return True

    # Object compatibility (pickle can produce anything)
    if produced_type == object:
        logger.debug(f"Object type check passed for '{data_source_name}' (dynamic type)")
        return True

    logger.warning(
        f"Type mismatch for '{data_source_name}': "
        f"expected {expected_type.__name__}, handler produces {produced_type.__name__}"
    )
    return False
