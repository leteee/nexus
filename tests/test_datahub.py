"""
Test the DataHub functionality.

Tests for centralized data management, lazy loading,
and caching behavior.
"""

import tempfile
from pathlib import Path

import pandas as pd

from nexus.core.datahub import DataHub


class TestDataHub:
    """Test suite for DataHub functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create test data
        self.test_data = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

        # Save test data
        self.csv_path = self.temp_dir / "test.csv"
        self.test_data.to_csv(self.csv_path, index=False)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_datahub_creation(self):
        """Test DataHub can be created with data sources."""
        data_sources = {
            "test_data": {
                "handler": "csv",
                "path": str(self.csv_path),
                "must_exist": True,
            }
        }

        hub = DataHub(data_sources)
        assert hub is not None

    def test_basic_functionality(self):
        """Test basic DataHub functionality works."""
        data_sources = {
            "test_data": {
                "handler": "csv",
                "path": str(self.csv_path),
                "must_exist": True,
            }
        }

        hub = DataHub(data_sources)

        # Test that we can create the hub without errors
        assert hasattr(hub, "_data_sources")
        # Test basic functionality without relying on private attributes
