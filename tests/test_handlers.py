"""
Test the data handlers functionality.

Tests for various data format handlers with proper error handling
and type safety validation.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from nexus.handlers import (
    CSVHandler, JSONHandler, PickleHandler, ParquetHandler,
    get_handler, register_handler, HANDLER_REGISTRY,
    DataHandler
)


class TestDataHandlers:
    """Test suite for data handlers."""

    def test_csv_handler(self):
        """Test CSV handler load and save operations."""
        handler = CSVHandler()

        # Create test data
        df = pd.DataFrame({
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [25, 30, 35],
            'city': ['NYC', 'LA', 'Chicago']
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.csv"

            # Test save
            handler.save(df, path)
            assert path.exists()

            # Test load
            loaded_df = handler.load(path)
            pd.testing.assert_frame_equal(df, loaded_df)

    def test_json_handler(self):
        """Test JSON handler load and save operations."""
        handler = JSONHandler()

        # Create test data
        data = {
            'users': [
                {'name': 'Alice', 'age': 25},
                {'name': 'Bob', 'age': 30}
            ],
            'metadata': {
                'version': '1.0',
                'created': '2024-01-01'
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            # Test save
            handler.save(data, path)
            assert path.exists()

            # Test load
            loaded_data = handler.load(path)
            assert loaded_data == data

    def test_pickle_handler(self):
        """Test Pickle handler load and save operations."""
        handler = PickleHandler()

        # Create test data (complex object)
        data = {
            'dataframe': pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]}),
            'list': [1, 2, 3, 4, 5],
            'nested': {'a': {'b': {'c': 'deep value'}}}
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.pkl"

            # Test save
            handler.save(data, path)
            assert path.exists()

            # Test load
            loaded_data = handler.load(path)
            assert isinstance(loaded_data, dict)
            pd.testing.assert_frame_equal(
                data['dataframe'],
                loaded_data['dataframe']
            )
            assert loaded_data['list'] == data['list']
            assert loaded_data['nested'] == data['nested']

    def test_parquet_handler(self):
        """Test Parquet handler load and save operations."""
        handler = ParquetHandler()

        # Create test data
        df = pd.DataFrame({
            'id': range(1000),
            'value': [x * 2.5 for x in range(1000)],
            'category': ['A', 'B', 'C'] * 333 + ['A']
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"

            # Test save
            handler.save(df, path)
            assert path.exists()

            # Test load
            loaded_df = handler.load(path)
            pd.testing.assert_frame_equal(df, loaded_df)

    def test_get_handler_registry(self):
        """Test handler registry functionality."""
        # Test getting existing handlers
        csv_handler = get_handler("csv")
        assert isinstance(csv_handler, CSVHandler)

        json_handler = get_handler("json")
        assert isinstance(json_handler, JSONHandler)

        pickle_handler = get_handler("pickle")
        assert isinstance(pickle_handler, PickleHandler)

        parquet_handler = get_handler("parquet")
        assert isinstance(parquet_handler, ParquetHandler)

    def test_get_unknown_handler_raises_error(self):
        """Test that getting unknown handler raises ValueError."""
        with pytest.raises(ValueError, match="No handler registered for file type: unknown"):
            get_handler("unknown")

    def test_register_custom_handler(self):
        """Test registering a custom handler."""
        class CustomHandler(DataHandler):
            def load(self, path: Path):
                return f"Loaded from {path}"

            def save(self, data, path: Path):
                path.write_text(str(data))

        register_handler("custom", CustomHandler)

        # Test the custom handler is registered
        handler = get_handler("custom")
        assert isinstance(handler, CustomHandler)

        # Test it works
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.custom"
            handler.save("test data", path)
            loaded = handler.load(path)
            assert loaded == f"Loaded from {path}"

    def test_handler_creates_parent_directories(self):
        """Test that handlers create parent directories when saving."""
        handler = JSONHandler()
        data = {"test": "data"}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested path that doesn't exist
            path = Path(tmpdir) / "nested" / "deep" / "test.json"

            # Should create directories and save file
            handler.save(data, path)
            assert path.exists()
            assert path.parent.exists()

            # Verify data was saved correctly
            loaded = handler.load(path)
            assert loaded == data