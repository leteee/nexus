"""
End-to-end integration tests for the Nexus framework.

These tests demonstrate the complete workflow with simplified architecture.
"""

import tempfile
from pathlib import Path

import pandas as pd

from nexus.core.discovery import plugin
from nexus.core.engine import PipelineEngine
from nexus.core.types import PluginConfig


class _TestDataProcessorConfig(PluginConfig):
    """Configuration for test data processor plugin."""

    multiplier: int = 2


# Remove test_ prefix to avoid pytest confusion
@plugin(name="Test Data Processor", config=_TestDataProcessorConfig)
def _test_data_processor_impl(context):
    """Simple test plugin that processes data."""
    # Return simple test data
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "value": [
                10 * context.config.multiplier,
                20 * context.config.multiplier,
                30 * context.config.multiplier,
            ],
        }
    )


class TestIntegration:
    """Integration tests for the simplified Nexus framework."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "project"
        self.case_dir = self.temp_dir / "case"

        # Create basic directory structure
        self.project_root.mkdir(parents=True)
        self.case_dir.mkdir(parents=True)

        # Create minimal config
        config_dir = self.project_root / "config"
        config_dir.mkdir()

        with open(config_dir / "global.yaml", "w") as f:
            f.write(
                """
framework:
  name: "nexus"
  cases_root: "cases"
"""
            )

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_pipeline_engine_creation(self):
        """Test that PipelineEngine can be created."""
        engine = PipelineEngine(self.project_root, self.case_dir)
        assert engine is not None
        assert engine.project_root == self.project_root
        assert engine.case_dir == self.case_dir

    def test_basic_plugin_execution(self):
        """Test basic plugin execution workflow."""
        engine = PipelineEngine(self.project_root, self.case_dir)

        # Test single plugin execution
        result = engine.run_single_plugin("Test Data Processor", {"multiplier": 3})

        # Verify result is a DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert result["value"].tolist() == [
            20,
            40,
            60,
        ]  # Default multiplier=2: 10*2, 20*2, 30*2
