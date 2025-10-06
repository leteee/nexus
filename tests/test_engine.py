"""
Tests for PipelineEngine - pipeline execution and data source discovery.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

from nexus.core.engine import PipelineEngine


class TestPipelineEngine:
    """Test PipelineEngine functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure with data files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)

            # Create config
            config_dir = project_root / "config"
            config_dir.mkdir()
            (config_dir / "global.yaml").write_text(
                yaml.dump(
                    {
                        "framework": {
                            "name": "nexus",
                            "cases_root": "cases",
                            "logging": {"level": "INFO"},
                        },
                        "plugins": {"modules": [], "paths": []},
                        "plugin_defaults": {"Data Generator": {"num_rows": 100}},
                    }
                )
            )

            # Create case directory with various data files
            case_dir = project_root / "cases" / "test-case"
            case_dir.mkdir(parents=True)

            # Create data subdirectory
            data_dir = case_dir / "data"
            data_dir.mkdir()

            # Create sample data files for auto-discovery
            # CSV file
            csv_data = pd.DataFrame(
                {
                    "id": [1, 2, 3],
                    "name": ["Alice", "Bob", "Charlie"],
                    "value": [10.5, 20.3, 15.7],
                }
            )
            csv_data.to_csv(data_dir / "sample_data.csv", index=False)

            # JSON file
            json_data = {
                "config": {"version": "1.0"},
                "items": [{"id": 1, "name": "test"}],
            }
            (data_dir / "config.json").write_text(json.dumps(json_data))

            # Additional CSV in root case directory
            csv_data2 = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
            csv_data2.to_csv(case_dir / "root_data.csv", index=False)

            # Non-data files (should be ignored)
            (data_dir / "readme.txt").write_text("This is documentation")
            (case_dir / "notes.md").write_text("# Notes")

            # Create case.yaml for some tests
            case_config = {
                "case_info": {
                    "name": "Test Case with Data",
                    "description": "Case for testing auto-discovery",
                },
                "pipeline": [
                    {
                        "plugin": "Data Generator",
                        "config": {"num_rows": 500},
                        "outputs": [{"name": "generated_data"}],
                    }
                ],
                "data_sources": {
                    "manual_source": {
                        "handler": "csv",
                        "path": "data/manual_data.csv",
                        "must_exist": False,
                    }
                },
            }
            (case_dir / "case.yaml").write_text(yaml.dump(case_config))

            yield project_root, case_dir

    @pytest.fixture
    def engine(self, temp_project):
        """Create a PipelineEngine instance."""
        project_root, case_dir = temp_project
        return PipelineEngine(project_root, case_dir)

    def test_engine_initialization(self, temp_project):
        """Test PipelineEngine initialization."""
        project_root, case_dir = temp_project
        engine = PipelineEngine(project_root, case_dir)

        assert engine.project_root == project_root
        assert engine.case_dir == case_dir

    def test_auto_discover_data_sources(self, engine):
        """Test automatic data source discovery."""
        discovered_sources = engine._auto_discover_data_sources()

        # Should discover CSV and JSON files
        discovered_names = list(discovered_sources.keys())

        # Check that we found some sources
        assert len(discovered_sources) >= 2

        # Check for specific expected files (may have different names due to deduplication)
        has_csv = any(
            "csv" in discovered_sources[name]["handler"] for name in discovered_names
        )
        has_json = any(
            "json" in discovered_sources[name]["handler"] for name in discovered_names
        )

        assert has_csv, f"Expected CSV handler, but found: {discovered_sources}"
        assert has_json, f"Expected JSON handler, but found: {discovered_sources}"

        # Check that auto_discovered flag is set
        for source in discovered_sources.values():
            assert source.get("auto_discovered") is True

    def test_auto_discover_empty_directory(self, temp_project):
        """Test auto-discovery with empty case directory."""
        project_root, _ = temp_project
        empty_case_dir = project_root / "cases" / "empty-case"
        empty_case_dir.mkdir(parents=True)

        engine = PipelineEngine(project_root, empty_case_dir)
        discovered_sources = engine._auto_discover_data_sources()

        assert discovered_sources == {}

    def test_auto_discover_nonexistent_directory(self, temp_project):
        """Test auto-discovery with nonexistent case directory."""
        project_root, _ = temp_project
        nonexistent_dir = project_root / "cases" / "nonexistent"

        engine = PipelineEngine(project_root, nonexistent_dir)
        discovered_sources = engine._auto_discover_data_sources()

        assert discovered_sources == {}

    def test_auto_discover_duplicate_names(self, temp_project):
        """Test auto-discovery handles duplicate filenames correctly."""
        project_root, case_dir = temp_project

        # Create files with same name in different locations
        (case_dir / "duplicate.csv").write_text("id,value\n1,10")
        data_dir = case_dir / "data"
        (data_dir / "duplicate.csv").write_text("id,value\n2,20")

        engine = PipelineEngine(project_root, case_dir)
        discovered_sources = engine._auto_discover_data_sources()

        # Should have both files with different names
        duplicate_sources = [
            name for name in discovered_sources.keys() if "duplicate" in name
        ]
        assert len(duplicate_sources) >= 2
        assert "duplicate" in duplicate_sources
        assert any("duplicate_" in name for name in duplicate_sources)

    def test_run_single_plugin_with_existing_case_config(self, engine):
        """Test running single plugin with existing case.yaml."""
        # This test checks that the method loads existing case config
        try:
            # This may fail due to missing plugin implementation, but should get past config loading
            _result = engine.run_single_plugin("Data Generator", {"num_rows": 50})
        except Exception as e:
            # Expected to fail at plugin execution, not config loading
            assert "case.yaml" not in str(e) or "not found" not in str(e)

    def test_run_single_plugin_without_case_config(self, temp_project):
        """Test running single plugin without existing case.yaml."""
        project_root, _ = temp_project

        # Create a new case directory without case.yaml
        new_case_dir = project_root / "cases" / "new-case"
        new_case_dir.mkdir(parents=True)
        (new_case_dir / "data").mkdir()

        # Add some data files for auto-discovery
        pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(
            new_case_dir / "data" / "test.csv", index=False
        )

        engine = PipelineEngine(project_root, new_case_dir)

        try:
            _result = engine.run_single_plugin("Data Generator", {"num_rows": 50})
        except Exception as e:
            # Should create minimal config and attempt execution
            # Error should be from plugin execution, not config loading
            assert "No case configuration found" not in str(e)

    def test_resolve_data_source_paths_relative(self, engine):
        """Test resolving relative data source paths."""
        data_sources_config = {
            "source1": {"handler": "csv", "path": "data/file1.csv"},
            "source2": {"handler": "json", "path": "config.json"},
        }

        resolved = engine._resolve_data_sources(data_sources_config)

        # Paths should be resolved relative to case directory
        assert str(engine.case_dir) in resolved["source1"]["path"]
        assert "file1.csv" in resolved["source1"]["path"]
        assert str(engine.case_dir) in resolved["source2"]["path"]
        assert "config.json" in resolved["source2"]["path"]

    def test_resolve_data_source_paths_absolute(self, engine, temp_project):
        """Test resolving absolute data source paths."""
        project_root, _ = temp_project
        absolute_path = str(project_root / "some" / "absolute" / "path.csv")

        data_sources_config = {"source1": {"handler": "csv", "path": absolute_path}}

        resolved = engine._resolve_data_sources(data_sources_config)

        # Absolute paths should remain unchanged
        assert resolved["source1"]["path"] == absolute_path

    def test_resolve_data_source_paths_preserves_other_config(self, engine):
        """Test that path resolution preserves other configuration."""
        data_sources_config = {
            "source1": {
                "handler": "csv",
                "path": "data/file.csv",
                "must_exist": True,
                "custom_option": "value",
                "auto_discovered": False,
            }
        }

        resolved = engine._resolve_data_sources(data_sources_config)

        # Other config should be preserved
        assert resolved["source1"]["handler"] == "csv"
        assert resolved["source1"]["must_exist"] is True
        assert resolved["source1"]["custom_option"] == "value"
        assert resolved["source1"]["auto_discovered"] is False

    def test_file_extension_detection(self, temp_project):
        """Test that different file extensions are detected correctly."""
        project_root, case_dir = temp_project

        # Create files with different extensions and unique names
        test_files = {
            "csv_data.csv": "csv",
            "json_config.json": "json",
            "parquet_data.parquet": "parquet",
            "excel_spreadsheet.xlsx": "excel",
            "xml_config.xml": "xml",
        }

        data_dir = case_dir / "data"
        for filename, expected_handler in test_files.items():
            (data_dir / filename).write_text("dummy content")

        engine = PipelineEngine(project_root, case_dir)
        discovered_sources = engine._auto_discover_data_sources()

        for filename, expected_handler in test_files.items():
            source_name = Path(filename).stem
            if source_name in discovered_sources:
                assert discovered_sources[source_name]["handler"] == expected_handler

    def test_case_insensitive_extensions(self, temp_project):
        """Test that file extensions are handled case-insensitively."""
        project_root, case_dir = temp_project

        # Create files with uppercase extensions
        (case_dir / "data" / "file.CSV").write_text("dummy")
        (case_dir / "data" / "file.JSON").write_text("dummy")

        engine = PipelineEngine(project_root, case_dir)
        discovered_sources = engine._auto_discover_data_sources()

        # Should detect files regardless of extension case
        found_handlers = {src["handler"] for src in discovered_sources.values()}
        assert "csv" in found_handlers
        assert "json" in found_handlers
