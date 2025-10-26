"""
Tests for CaseManager - case and template management functionality.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from nexus.core.case_manager import CaseManager


class TestCaseManager:
    """Test CaseManager functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)

            # Create templates directory with sample templates
            templates_dir = project_root / "templates"
            templates_dir.mkdir()

            # Create default template
            default_template = {
                "case_info": {
                    "name": "Default Template",
                    "description": "Basic processing pipeline",
                },
                "pipeline": [
                    {
                        "plugin": "Data Generator",
                        "config": {"num_rows": 1000},
                        "outputs": [{"name": "generated_data"}],
                    }
                ],
            }
            (templates_dir / "default.yaml").write_text(yaml.dump(default_template))

            # Create analytics template
            analytics_template = {
                "case_info": {
                    "name": "Analytics Template",
                    "description": "Analytics pipeline",
                },
                "pipeline": [
                    {
                        "plugin": "Data Aggregator",
                        "config": {"group_by": "category"},
                        "outputs": [{"name": "aggregated_data"}],
                    }
                ],
            }
            (templates_dir / "analytics.yaml").write_text(yaml.dump(analytics_template))

            # Create cases directory
            cases_dir = project_root / "cases"
            cases_dir.mkdir()

            # Create an existing case with case.yaml
            existing_case_dir = cases_dir / "existing-case"
            existing_case_dir.mkdir()
            (existing_case_dir / "data").mkdir()

            existing_case_config = {
                "case_info": {
                    "name": "Existing Case",
                    "description": "A case that already exists",
                },
                "pipeline": [
                    {
                        "plugin": "Data Validator",
                        "outputs": [{"name": "validation_report"}],
                    }
                ],
            }
            (existing_case_dir / "case.yaml").write_text(
                yaml.dump(existing_case_config)
            )

            yield project_root

    @pytest.fixture
    def case_manager(self, temp_project):
        """Create a CaseManager instance."""
        return CaseManager(temp_project, "cases")

    def test_case_manager_initialization(self, temp_project):
        """Test CaseManager initialization."""
        case_manager = CaseManager(temp_project, "cases")

        assert case_manager.project_root == temp_project
        assert case_manager.cases_root == temp_project / "cases"
        # templates_dir is managed internally through global.yaml discovery config
        # Not exposed as a public attribute

    def test_case_manager_custom_cases_root(self, temp_project):
        """Test CaseManager with custom cases root."""
        # Create custom cases directory
        custom_cases_dir = temp_project / "my_cases"
        custom_cases_dir.mkdir()

        case_manager = CaseManager(temp_project, "my_cases")
        assert case_manager.cases_root == temp_project / "my_cases"

    def test_resolve_case_path_relative(self, case_manager):
        """Test resolving relative case paths."""
        result = case_manager.resolve_case_path("my-case")
        expected = case_manager.cases_root / "my-case"
        assert result == expected

    def test_resolve_case_path_absolute(self, case_manager, temp_project):
        """Test resolving absolute case paths."""
        absolute_path = temp_project / "somewhere" / "else" / "my-case"
        result = case_manager.resolve_case_path(str(absolute_path))
        assert result == absolute_path

    def test_list_available_templates(self, case_manager):
        """Test listing available templates."""
        templates = case_manager.list_available_templates()
        assert "default" in templates
        assert "analytics" in templates
        assert len(templates) == 2

    def test_list_available_templates_empty_dir(self, temp_project):
        """Test listing templates when templates directory doesn't exist."""
        # Remove templates directory
        shutil.rmtree(temp_project / "templates")
        case_manager = CaseManager(temp_project, "cases")

        templates = case_manager.list_available_templates()
        assert templates == []

    def test_list_existing_cases(self, case_manager):
        """Test listing existing cases."""
        cases = case_manager.list_existing_cases()
        assert "existing-case" in cases
        assert len(cases) == 1

    def test_list_existing_cases_empty_dir(self, temp_project):
        """Test listing cases when cases directory doesn't exist."""
        # Remove cases directory
        shutil.rmtree(temp_project / "cases")
        case_manager = CaseManager(temp_project, "cases")

        cases = case_manager.list_existing_cases()
        assert cases == []

    def test_get_case_config_existing_case_no_template(self, case_manager):
        """Test getting pipeline config for existing case without template."""
        config_path, config_data = case_manager.get_case_config("existing-case")

        assert config_path.name == "case.yaml"
        assert "existing-case" in str(config_path)
        assert config_data["case_info"]["name"] == "Existing Case"

    def test_get_case_config_new_case_with_template(self, case_manager):
        """Test getting pipeline config for new case with template (template mode)."""
        config_path, config_data = case_manager.get_case_config(
            "new-case", "default"
        )

        # Should use template directly, not copy to case.yaml
        assert config_path.name == "default.yaml"
        assert "templates" in str(config_path)
        assert config_data["case_info"]["name"] == "Default Template"

        # case.yaml should NOT be created (template replaces it)
        new_case_yaml = case_manager.resolve_case_path("new-case") / "case.yaml"
        assert not new_case_yaml.exists()

    def test_get_case_config_existing_case_with_template(self, case_manager):
        """Test getting pipeline config for existing case with template (template mode)."""
        config_path, config_data = case_manager.get_case_config(
            "existing-case", "analytics"
        )

        # Should use template directly, case.yaml completely ignored
        assert config_path.name == "analytics.yaml"
        assert "templates" in str(config_path)
        assert config_data["case_info"]["name"] == "Analytics Template"

        # Original case.yaml should remain unchanged (but ignored)
        original_case_yaml = (
            case_manager.resolve_case_path("existing-case") / "case.yaml"
        )
        original_config = yaml.safe_load(original_case_yaml.read_text())
        assert original_config["case_info"]["name"] == "Existing Case"

    def test_get_case_config_missing_case_no_template(self, case_manager):
        """Test getting pipeline config for missing case without template."""
        with pytest.raises(FileNotFoundError) as exc_info:
            case_manager.get_case_config("nonexistent-case")

        assert "No case configuration found" in str(exc_info.value)
        assert "specify a template" in str(exc_info.value)

    def test_get_case_config_invalid_template(self, case_manager):
        """Test getting pipeline config with invalid template name."""
        with pytest.raises(FileNotFoundError) as exc_info:
            case_manager.get_case_config("some-case", "nonexistent-template")

        assert "Template 'nonexistent-template' not found" in str(exc_info.value)
        assert "Available templates:" in str(exc_info.value)

    def test_template_name_with_yaml_extension(self, case_manager):
        """Test template names with .yaml extension are handled correctly."""
        config_path, config_data = case_manager.get_case_config(
            "test-case", "default.yaml"
        )

        # Should work the same as without extension
        assert config_data["case_info"]["name"] == "Default Template"

    def test_case_directory_creation(self, case_manager):
        """Test that case directories are created automatically."""
        case_path = "deeply/nested/new-case"
        config_path, config_data = case_manager.get_case_config(
            case_path, "default"
        )

        # Directory should be created
        expected_dir = case_manager.resolve_case_path(case_path)
        assert expected_dir.exists()
        assert expected_dir.is_dir()

    def test_invalid_yaml_handling(self, case_manager, temp_project):
        """Test handling of invalid YAML files."""
        # Create a case with invalid YAML
        bad_case_dir = temp_project / "cases" / "bad-case"
        bad_case_dir.mkdir()
        (bad_case_dir / "case.yaml").write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError) as exc_info:
            case_manager.get_case_config("bad-case")

        assert "Invalid YAML" in str(exc_info.value)

    def test_empty_yaml_handling(self, case_manager, temp_project):
        """Test handling of empty YAML files."""
        # Create a case with empty YAML
        empty_case_dir = temp_project / "cases" / "empty-case"
        empty_case_dir.mkdir()
        (empty_case_dir / "case.yaml").write_text("")

        config_path, config_data = case_manager.get_case_config("empty-case")

        # Should return empty dict for empty YAML
        assert config_data == {}

    def test_find_template_case_sensitivity(self, case_manager):
        """Test template finding with different cases."""
        # Template exists as "default.yaml"
        template_path = case_manager._find_template("default")
        assert template_path.exists()

        # Should still work with exact filename
        template_path = case_manager._find_template("default.yaml")
        assert template_path.exists()

    def test_cases_in_subdirectories(self, case_manager, temp_project):
        """Test handling cases in subdirectories."""
        # Create nested case structure
        nested_dir = temp_project / "cases" / "project1" / "analysis1"
        nested_dir.mkdir(parents=True)

        nested_config = {"case_info": {"name": "Nested Case"}, "pipeline": []}
        (nested_dir / "case.yaml").write_text(yaml.dump(nested_config))

        # Should be able to access with relative path
        config_path, config_data = case_manager.get_case_config(
            "project1/analysis1"
        )
        assert config_data["case_info"]["name"] == "Nested Case"

