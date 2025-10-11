"""
Data handlers for different file formats.

This module provides handler implementations for common data formats:
- CSV files (pandas DataFrame)
- JSON files (dict)
- Pickle files (any Python object)
- Parquet files (pandas DataFrame)

Each handler is automatically registered with the core handler registry.
"""

import json
import pickle
from pathlib import Path
from typing import Any

import pandas as pd

from nexus.core.types import DataHandler
from nexus.core.handlers import register_handler

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


# Register all handlers with the core registry
register_handler("csv", CSVHandler)
register_handler("json", JSONHandler)
register_handler("pickle", PickleHandler)
register_handler("pkl", PickleHandler)  # Alias for pickle
register_handler("parquet", ParquetHandler)
