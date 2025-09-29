"""
Data handlers for different file formats.

Following data_replay's handler protocol with type safety.
Each handler declares its produced type for runtime type checking.
"""

import json
import pickle
from pathlib import Path
from typing import Any, Dict, Type

import pandas as pd

from .types import DataHandler

logger = __import__("logging").getLogger(__name__)


class CSVHandler:
    """Handler for CSV files using pandas."""

    @property
    def produced_type(self) -> type:
        return pd.DataFrame

    def load(self, path: Path) -> pd.DataFrame:
        """Load CSV file as pandas DataFrame."""
        try:
            return pd.read_csv(path)
        except Exception as e:
            logger.error(f"Failed to load CSV from {path}: {e}")
            raise

    def save(self, data: pd.DataFrame, path: Path) -> None:
        """Save DataFrame as CSV file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(path, index=False)
        except Exception as e:
            logger.error(f"Failed to save CSV to {path}: {e}")
            raise


class JSONHandler:
    """Handler for JSON files."""

    @property
    def produced_type(self) -> type:
        return dict

    def load(self, path: Path) -> Any:
        """Load JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load JSON from {path}: {e}")
            raise

    def save(self, data: Any, path: Path) -> None:
        """Save data as JSON file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save JSON to {path}: {e}")
            raise


class PickleHandler:
    """Handler for pickle files."""

    @property
    def produced_type(self) -> type:
        return object

    def load(self, path: Path) -> Any:
        """Load pickle file."""
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Failed to load pickle from {path}: {e}")
            raise

    def save(self, data: Any, path: Path) -> None:
        """Save data as pickle file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save pickle to {path}: {e}")
            raise


class ParquetHandler:
    """Handler for Parquet files using pandas."""

    @property
    def produced_type(self) -> type:
        return pd.DataFrame

    def load(self, path: Path) -> pd.DataFrame:
        """Load Parquet file as pandas DataFrame."""
        try:
            return pd.read_parquet(path)
        except Exception as e:
            logger.error(f"Failed to load Parquet from {path}: {e}")
            raise

    def save(self, data: pd.DataFrame, path: Path) -> None:
        """Save DataFrame as Parquet file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data.to_parquet(path)
        except Exception as e:
            logger.error(f"Failed to save Parquet to {path}: {e}")
            raise


# Handler registry mapping file extensions to handler classes
HANDLER_REGISTRY: Dict[str, Type[DataHandler]] = {
    "csv": CSVHandler,
    "json": JSONHandler,
    "pickle": PickleHandler,
    "pkl": PickleHandler,
    "parquet": ParquetHandler,
}


def get_handler(handler_type: str) -> DataHandler:
    """
    Get handler instance by type.

    Args:
        handler_type: Type of handler (e.g., 'csv', 'json')

    Returns:
        Handler instance

    Raises:
        ValueError: If handler type is not registered
    """
    if handler_type not in HANDLER_REGISTRY:
        raise ValueError(f"Unknown handler type: {handler_type}")

    handler_class = HANDLER_REGISTRY[handler_type]
    return handler_class()


def register_handler(handler_type: str, handler_class: Type[DataHandler]) -> None:
    """
    Register a new data handler.

    Args:
        handler_type: Type identifier for the handler
        handler_class: Handler class implementing DataHandler protocol
    """
    HANDLER_REGISTRY[handler_type] = handler_class
    logger.info(f"Registered handler '{handler_type}': {handler_class.__name__}")


def get_handler_for_path(path: Path) -> DataHandler:
    """
    Get appropriate handler based on file extension.

    Args:
        path: File path

    Returns:
        Handler instance

    Raises:
        ValueError: If no handler found for file extension
    """
    suffix = path.suffix.lstrip(".")
    if suffix in HANDLER_REGISTRY:
        return get_handler(suffix)

    # Try common aliases
    if suffix in ["pkl"]:
        return get_handler("pickle")

    raise ValueError(f"No handler found for file extension: {suffix}")


def preflight_type_check(
    data_source_name: str, expected_type: type, handler: DataHandler
) -> bool:
    """
    Perform type compatibility check between handler and expected type.

    Args:
        data_source_name: Name of data source for logging
        expected_type: Expected data type
        handler: Data handler instance

    Returns:
        True if types are compatible, False otherwise
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