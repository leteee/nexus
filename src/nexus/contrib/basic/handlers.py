"""
Data handlers for common file formats.

Handlers register themselves via @handler decorator and are
automatically discovered when this module is imported.
"""

import json
import pickle
from pathlib import Path
from typing import Any

import pandas as pd

from nexus.core.handlers import handler

logger = __import__("logging").getLogger(__name__)


@handler("csv")
class CSVHandler:
    """Handler for CSV files using pandas."""

    @property
    def produced_type(self) -> type:
        return pd.DataFrame

    def load(self, path: Path) -> pd.DataFrame:
        try:
            return pd.read_csv(path)
        except Exception as e:
            logger.error(f"Failed to load CSV from {path}: {e}")
            raise

    def save(self, data: pd.DataFrame, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(path, index=False)
        except Exception as e:
            logger.error(f"Failed to save CSV to {path}: {e}")
            raise


@handler("json")
class JSONHandler:
    """Handler for JSON files."""

    @property
    def produced_type(self) -> type:
        return dict

    def load(self, path: Path) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load JSON from {path}: {e}")
            raise

    def save(self, data: Any, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to save JSON to {path}: {e}")
            raise


@handler("pickle")
@handler("pkl")
class PickleHandler:
    """Handler for pickle files."""

    @property
    def produced_type(self) -> type:
        return object

    def load(self, path: Path) -> Any:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Failed to load pickle from {path}: {e}")
            raise

    def save(self, data: Any, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save pickle to {path}: {e}")
            raise


@handler("parquet")
class ParquetHandler:
    """Handler for Parquet files using pandas."""

    @property
    def produced_type(self) -> type:
        return pd.DataFrame

    def load(self, path: Path) -> pd.DataFrame:
        try:
            return pd.read_parquet(path)
        except Exception as e:
            logger.error(f"Failed to load Parquet from {path}: {e}")
            raise

    def save(self, data: pd.DataFrame, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data.to_parquet(path)
        except Exception as e:
            logger.error(f"Failed to save Parquet to {path}: {e}")
            raise
