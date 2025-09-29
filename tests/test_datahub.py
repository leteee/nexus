"""
Test the DataHub functionality.

Tests for centralized data management, lazy loading,
and caching behavior.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from nexus.datahub import DataHub, DataSource


class TestDataHub:
    """Test suite for DataHub functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.tmpdir = tempfile.mkdtemp()
        self.case_path = Path(self.tmpdir)
        self.hub = DataHub(self.case_path)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_register_and_get_data_source(self):
        """Test registering and getting a data source."""
        # Create test CSV file
        df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})
        csv_path = self.case_path / "test.csv"
        df.to_csv(csv_path, index=False)

        # Register data source
        self.hub.register_source("test_data", "test.csv", "csv")

        # Get data (should load and cache)
        loaded_df = self.hub.get("test_data")
        pd.testing.assert_frame_equal(df, loaded_df)

        # Get again (should return cached version)
        cached_df = self.hub.get("test_data")
        pd.testing.assert_frame_equal(df, cached_df)

    def test_absolute_path_handling(self):
        """Test that absolute paths are handled correctly."""
        df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        abs_path = Path(self.tmpdir) / "absolute_test.csv"
        df.to_csv(abs_path, index=False)

        # Register with absolute path
        self.hub.register_source("abs_data", str(abs_path), "csv")

        loaded_df = self.hub.get("abs_data")
        pd.testing.assert_frame_equal(df, loaded_df)

    def test_relative_path_resolution(self):
        """Test that relative paths are resolved correctly."""
        df = pd.DataFrame({'col1': ['a', 'b'], 'col2': [1, 2]})
        rel_path = self.case_path / "subdir" / "relative_test.csv"
        rel_path.parent.mkdir(exist_ok=True)
        df.to_csv(rel_path, index=False)

        # Register with relative path
        self.hub.register_source("rel_data", "subdir/relative_test.csv", "csv")

        loaded_df = self.hub.get("rel_data")
        pd.testing.assert_frame_equal(df, loaded_df)

    def test_must_exist_flag(self):
        """Test must_exist flag behavior."""
        # Register non-existent file with must_exist=True (default)
        self.hub.register_source("missing_required", "missing.csv", "csv", must_exist=True)

        with pytest.raises(FileNotFoundError):
            self.hub.get("missing_required")

        # Register non-existent file with must_exist=False
        self.hub.register_source("missing_optional", "missing2.csv", "csv", must_exist=False)

        # Should not raise an error, but handler might
        # (depends on handler implementation)

    def test_save_data(self):
        """Test saving data to a specified path."""
        data = pd.DataFrame({'saved': [1, 2, 3], 'data': [4, 5, 6]})

        # Save data
        self.hub.save("saved_data", data, "output/saved.csv", "csv")

        # Verify file was created
        output_path = self.case_path / "output" / "saved.csv"
        assert output_path.exists()

        # Verify data was cached
        cached_data = self.hub.get("saved_data")
        pd.testing.assert_frame_equal(data, cached_data)

    def test_get_unregistered_source_raises_error(self):
        """Test that getting unregistered source raises KeyError."""
        with pytest.raises(KeyError, match="Data source 'unregistered' not registered"):
            self.hub.get("unregistered")

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        # Create and load data
        df = pd.DataFrame({'x': [1, 2, 3]})
        csv_path = self.case_path / "cache_test.csv"
        df.to_csv(csv_path, index=False)

        self.hub.register_source("cache_data", "cache_test.csv", "csv")
        loaded_df = self.hub.get("cache_data")  # Load into cache

        # Verify data is cached
        assert "cache_data" in self.hub._data

        # Clear cache
        self.hub.clear_cache()

        # Verify cache is empty
        assert len(self.hub._data) == 0

        # Verify data can still be loaded
        reloaded_df = self.hub.get("cache_data")
        pd.testing.assert_frame_equal(df, reloaded_df)

    def test_list_sources(self):
        """Test listing all registered sources."""
        # Register multiple sources
        self.hub.register_source("source1", "file1.csv", "csv")
        self.hub.register_source("source2", "file2.json", "json")

        sources = self.hub.list_sources()
        assert "source1" in sources
        assert "source2" in sources
        assert sources["source1"] == str(self.case_path / "file1.csv")
        assert sources["source2"] == str(self.case_path / "file2.json")

    def test_json_data_handling(self):
        """Test handling JSON data through DataHub."""
        data = {"name": "test", "values": [1, 2, 3, 4, 5]}
        json_path = self.case_path / "test.json"

        # Save JSON data using handler directly
        from nexus.handlers import JSONHandler
        handler = JSONHandler()
        handler.save(data, json_path)

        # Register and load through DataHub
        self.hub.register_source("json_data", "test.json", "json")
        loaded_data = self.hub.get("json_data")

        assert loaded_data == data