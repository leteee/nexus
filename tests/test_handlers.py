"""
Test the data handlers functionality.

Tests for various data format handlers with proper error handling
and type safety validation.
"""

import tempfile
from pathlib import Path

import pandas as pd

from nexus.core.handlers import HANDLER_REGISTRY, CSVHandler, JSONHandler, get_handler


class TestDataHandlers:
    """Test suite for data handlers."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_data = {"key": "value", "number": 42}
        self.test_df = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_csv_handler_exists(self):
        """Test that CSV handler can be retrieved."""
        handler = get_handler("csv")
        assert isinstance(handler, CSVHandler)

    def test_json_handler_exists(self):
        """Test that JSON handler can be retrieved."""
        handler = get_handler("json")
        assert isinstance(handler, JSONHandler)

    def test_handlers_registered(self):
        """Test that handlers are properly registered."""
        assert "csv" in HANDLER_REGISTRY
        assert "json" in HANDLER_REGISTRY
        assert "pickle" in HANDLER_REGISTRY
        assert "parquet" in HANDLER_REGISTRY

    def test_json_round_trip(self):
        """Test JSON handler save and load."""
        handler = JSONHandler()
        json_path = self.temp_dir / "test.json"

        # Save data
        handler.save(self.test_data, json_path)
        assert json_path.exists()

        # Load data
        loaded_data = handler.load(json_path)
        assert loaded_data == self.test_data

    def test_csv_round_trip(self):
        """Test CSV handler save and load."""
        handler = CSVHandler()
        csv_path = self.temp_dir / "test.csv"

        # Save data
        handler.save(self.test_df, csv_path)
        assert csv_path.exists()

        # Load data
        loaded_df = handler.load(csv_path)
        pd.testing.assert_frame_equal(loaded_df, self.test_df)
