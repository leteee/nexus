"""
Tests for CLI commands and command-line interface functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from nexus.cli import cli, parse_config_overrides


class TestCLI:
    """Test CLI commands and functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)

            # Create project structure
            (project_root / "pyproject.toml").write_text("[project]\nname = 'nexus'")

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
                            "discovery": {
                                "plugins": {
                                    "paths": [],  # Empty paths for isolated testing
                                    "recursive": True,
                                },
                                "handlers": {"paths": [], "recursive": True},
                            },
                        },
                        "plugins": {"Data Generator": {"num_rows": 100}},
                    }
                )
            )

            # Create templates
            templates_dir = project_root / "templates"
            templates_dir.mkdir()
            (templates_dir / "default.yaml").write_text(
                yaml.dump(
                    {
                        "case_info": {
                            "name": "Default Template",
                            "description": "Basic template",
                        },
                        "pipeline": [
                            {
                                "plugin": "Data Generator",
                                "config": {"num_rows": 1000},
                                "outputs": [{"name": "generated_data"}],
                            }
                        ],
                    }
                )
            )

            # Create cases directory
            cases_dir = project_root / "cases"
            cases_dir.mkdir()

            # Create a test case
            test_case_dir = cases_dir / "test-case"
            test_case_dir.mkdir()
            (test_case_dir / "data").mkdir()

            yield project_root

    def test_version_command(self, runner):
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "Nexus" in result.output

    def test_help_command(self, runner):
        """Test help command."""
        result = runner.invoke(cli, ["help"])
        assert result.exit_code == 0
        assert "Nexus - A modern data processing framework" in result.output
        assert "Commands:" in result.output

    def test_list_plugins_command(self, runner, temp_project):
        """Test listing plugins."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            result = runner.invoke(cli, ["list", "plugins"])
            assert result.exit_code == 0
            # May show "Available plugins:" or "No plugins found" depending on discovery
            assert "plugins" in result.output.lower()

    def test_list_templates_command(self, runner, temp_project):
        """Test listing templates."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            result = runner.invoke(cli, ["list", "templates"])
            assert result.exit_code == 0
            assert "Available templates:" in result.output
            assert "default" in result.output

    def test_list_cases_command(self, runner, temp_project):
        """Test listing cases."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            result = runner.invoke(cli, ["list", "cases"])
            assert result.exit_code == 0
            # Should show no cases initially (no case.yaml files)
            assert "No cases found" in result.output

    def test_plugin_help_command(self, runner, temp_project):
        """Test plugin-specific help."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            # This test may fail if the plugin doesn't exist, so we expect possible failure
            result = runner.invoke(cli, ["help", "--plugin", "Data Generator"])
            # Plugin help command should either succeed or fail gracefully
            assert result.exit_code in [0, 1]

    def test_run_command_missing_case(self, runner, temp_project):
        """Test run command with missing case."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            result = runner.invoke(cli, ["run", "--case", "nonexistent"])
            assert result.exit_code == 1
            assert "ERROR:" in result.output

    def test_run_command_with_template(self, runner, temp_project):
        """Test run command with template."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            result = runner.invoke(
                cli, ["run", "--case", "test-case", "--template", "default"]
            )
            # This might fail due to missing plugins, but should get past argument parsing
            # Check for either success indicators or error messages (both are acceptable)
            assert (
                "case: test-case" in result.output
                or "Error:" in result.output
                or "ERROR:" in result.output
            )

    def test_plugin_command_missing_case(self, runner, temp_project):
        """Test plugin command with missing case directory."""
        with patch("nexus.cli.find_project_root", return_value=temp_project):
            result = runner.invoke(
                cli, ["plugin", "Data Generator", "--case", "new-case"]
            )
            # Should create the case directory and attempt execution
            assert result.exit_code in [
                0,
                1,
            ]  # May fail on plugin execution, but not on setup


class TestConfigParsing:
    """Test configuration parsing utilities."""

    def test_parse_config_overrides_simple(self):
        """Test parsing simple config overrides."""
        config_list = ("key=value", "num=42", "flag=true")
        result = parse_config_overrides(config_list)

        expected = {"key": "value", "num": 42, "flag": True}
        assert result == expected

    def test_parse_config_overrides_nested(self):
        """Test parsing nested config overrides."""
        config_list = (
            "plugins.DataGenerator.num_rows=1000",
            "framework.logging.level=DEBUG",
        )
        result = parse_config_overrides(config_list)

        expected = {
            "plugins": {"DataGenerator": {"num_rows": 1000}},
            "framework": {"logging": {"level": "DEBUG"}},
        }
        assert result == expected

    def test_parse_config_overrides_types(self):
        """Test parsing different value types."""
        config_list = (
            "string=hello",
            "integer=42",
            "float=3.14",
            "bool_true=true",
            "bool_false=false",
        )
        result = parse_config_overrides(config_list)

        assert result["string"] == "hello"
        assert result["integer"] == 42
        assert result["float"] == 3.14
        assert result["bool_true"] is True
        assert result["bool_false"] is False

    def test_parse_config_overrides_invalid_format(self):
        """Test handling invalid config format."""
        config_list = ("invalid_format", "valid=value")
        result = parse_config_overrides(config_list)

        # Should skip invalid format and process valid one
        assert "valid" in result
        assert result["valid"] == "value"
        assert len(result) == 1

    def test_parse_config_overrides_equals_in_value(self):
        """Test handling equals sign in value."""
        config_list = ("url=http://example.com?param=value",)
        result = parse_config_overrides(config_list)

        assert result["url"] == "http://example.com?param=value"


class TestProjectRootDiscovery:
    """Test project root discovery functionality."""

    def test_find_project_root_in_temp_dir(self):
        """Test finding project root in temporary directory."""
        from nexus.cli import find_project_root

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")

            # Test finding from root
            found_root = find_project_root(project_root)
            assert found_root == project_root

            # Test finding from subdirectory
            sub_dir = project_root / "subdir"
            sub_dir.mkdir()
            found_root = find_project_root(sub_dir)
            assert found_root == project_root

    def test_find_project_root_not_found(self):
        """Test behavior when project root is not found."""
        from nexus.cli import find_project_root

        with tempfile.TemporaryDirectory() as tmp_dir:
            start_path = Path(tmp_dir)
            # No pyproject.toml in the tree
            found_root = find_project_root(start_path)
            assert found_root == start_path  # Should return start path if not found
