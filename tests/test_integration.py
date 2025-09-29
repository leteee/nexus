"""
End-to-end integration tests for the Nexus framework.

These tests demonstrate the complete workflow from plugin registration
through pipeline execution, following real-world usage patterns.
"""

import tempfile
from pathlib import Path
from typing import Annotated

import pandas as pd
import pytest

from nexus.plugins import plugin
from nexus.typing import PluginConfig, DataSource, DataSink
from nexus.engine import PipelineEngine


class DataProcessorConfig(PluginConfig):
    """Configuration for data processing plugin."""
    input_data: Annotated[pd.DataFrame, DataSource(name="raw_data")]
    multiplier: float = 2.0


class FilterConfig(PluginConfig):
    """Configuration for data filtering plugin."""
    processed_data: Annotated[pd.DataFrame, DataSource(name="processed_data")]
    threshold: int = 10


class TestEndToEndWorkflow:
    """End-to-end tests for complete pipeline workflows."""

    def setup_method(self):
        """Set up test environment with sample data and plugins."""
        self.tmpdir = tempfile.mkdtemp()
        self.case_path = Path(self.tmpdir)

        # Create sample data
        self.sample_data = pd.DataFrame({
            'id': range(1, 21),
            'value': [x * 1.5 for x in range(1, 21)],
            'category': ['A', 'B'] * 10
        })

        # Save sample data
        data_path = self.case_path / "raw_data.csv"
        self.sample_data.to_csv(data_path, index=False)

        # Register test plugins
        self._register_test_plugins()

    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.tmpdir)

        # Clear plugin registry
        from nexus.plugins import PLUGIN_REGISTRY
        PLUGIN_REGISTRY.clear()

    def _register_test_plugins(self):
        """Register plugins for testing."""

        @plugin(name="Data Processor", config=DataProcessorConfig)
        def process_data(config: DataProcessorConfig, logger):
            """Process input data by applying a multiplier."""
            logger.info(f"Processing {len(config.input_data)} rows with multiplier {config.multiplier}")
            result = config.input_data.copy()
            result['value'] = result['value'] * config.multiplier
            return result

        @plugin(name="Data Filter", config=FilterConfig)
        def filter_data(config: FilterConfig, logger):
            """Filter data based on threshold."""
            logger.info(f"Filtering data with threshold {config.threshold}")
            return config.processed_data[config.processed_data['value'] > config.threshold]

        @plugin(name="Simple Counter")
        def count_rows(context):
            """Count rows in a dataset."""
            data = context.datahub.get("filtered_data")
            count = len(data)
            context.logger.info(f"Counted {count} rows")
            return count

    def test_single_plugin_execution(self):
        """Test running a single plugin."""
        engine = PipelineEngine(self.case_path)

        # Register data source manually for this test
        engine.datahub.register_source("raw_data", "raw_data.csv", "csv")

        # Run single plugin
        result = engine.run_plugin("Data Processor", {"multiplier": 3.0})

        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(self.sample_data)
        # Values should be multiplied by 3.0
        expected_values = self.sample_data['value'] * 3.0
        pd.testing.assert_series_equal(result['value'], expected_values, check_names=False)

    def test_pipeline_with_yaml_config(self):
        """Test running a complete pipeline with YAML configuration."""
        # Create pipeline configuration
        pipeline_config = {
            'data_sources': {
                'raw_data': {
                    'path': 'raw_data.csv',
                    'handler': 'csv'
                }
            },
            'pipeline': [
                {
                    'plugin': 'Data Processor',
                    'config': {
                        'multiplier': 2.5
                    },
                    'output': {
                        'processed_data': {
                            'path': 'processed_data.csv',
                            'handler': 'csv'
                        }
                    }
                },
                {
                    'plugin': 'Data Filter',
                    'config': {
                        'threshold': 15
                    },
                    'output': {
                        'filtered_data': {
                            'path': 'filtered_data.csv',
                            'handler': 'csv'
                        }
                    }
                }
            ]
        }

        # Save pipeline configuration
        import yaml
        config_path = self.case_path / "pipeline.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(pipeline_config, f)

        # Run pipeline
        engine = PipelineEngine(self.case_path)
        engine.run_pipeline()

        # Verify output files were created
        assert (self.case_path / "processed_data.csv").exists()
        assert (self.case_path / "filtered_data.csv").exists()

        # Verify processed data
        processed_data = pd.read_csv(self.case_path / "processed_data.csv")
        expected_processed = self.sample_data.copy()
        expected_processed['value'] = expected_processed['value'] * 2.5
        pd.testing.assert_frame_equal(processed_data, expected_processed)

        # Verify filtered data
        filtered_data = pd.read_csv(self.case_path / "filtered_data.csv")
        assert len(filtered_data) > 0
        assert all(filtered_data['value'] > 15)

    def test_plugin_chain_data_flow(self):
        """Test that data flows correctly between chained plugins."""
        engine = PipelineEngine(self.case_path)

        # Register initial data source
        engine.datahub.register_source("raw_data", "raw_data.csv", "csv")

        # Run first plugin and save result
        result1 = engine.run_plugin("Data Processor", {"multiplier": 2.0})
        engine.datahub.save("processed_data", result1, "intermediate.csv", "csv")

        # Register the intermediate result as a data source
        engine.datahub.register_source("processed_data", "intermediate.csv", "csv")

        # Run second plugin
        result2 = engine.run_plugin("Data Filter", {"threshold": 5.0})

        # Verify the chain worked correctly
        assert len(result2) <= len(result1)  # Filtering should reduce or maintain size
        assert all(result2['value'] > 5.0)   # All values should exceed threshold

    def test_error_handling_missing_data_source(self):
        """Test error handling when data source is missing."""
        engine = PipelineEngine(self.case_path)

        # Try to run plugin without registering data source
        with pytest.raises((KeyError, FileNotFoundError)):
            engine.run_plugin("Data Processor")

    def test_error_handling_invalid_plugin(self):
        """Test error handling for non-existent plugin."""
        engine = PipelineEngine(self.case_path)

        with pytest.raises(ValueError, match="Plugin 'Nonexistent Plugin' not found"):
            engine.run_plugin("Nonexistent Plugin")

    def test_different_data_formats(self):
        """Test pipeline with different data formats."""
        # Create JSON data
        json_data = {
            'items': [
                {'name': 'item1', 'count': 5},
                {'name': 'item2', 'count': 10},
                {'name': 'item3', 'count': 15}
            ]
        }

        json_path = self.case_path / "data.json"
        import json
        with open(json_path, 'w') as f:
            json.dump(json_data, f)

        # Register plugin that works with JSON
        @plugin(name="JSON Processor")
        def process_json(context):
            """Process JSON data."""
            data = context.datahub.get("json_data")
            total_count = sum(item['count'] for item in data['items'])
            context.logger.info(f"Total count: {total_count}")
            return total_count

        engine = PipelineEngine(self.case_path)
        engine.datahub.register_source("json_data", "data.json", "json")

        result = engine.run_plugin("JSON Processor")
        assert result == 30  # 5 + 10 + 15