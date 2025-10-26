"""
Test the simplified configuration system.

Tests verify that configuration hierarchy works correctly:
CLI > Case > Global > Plugin defaults
"""

import tempfile
from pathlib import Path

import yaml

from nexus.core.config import (
    create_configuration_context,
    deep_merge,
    load_global_configuration,
    load_yaml,
)
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig


class _TestPluginConfig(PluginConfig):
    """Test configuration model."""

    test_value: int = 42
    test_string: str = "default"


# Remove test_plugin function since it's being misinterpreted as a test by pytest
# It's just a plugin definition for testing purposes


@plugin(name="Test Plugin", config=_TestPluginConfig)
def _test_plugin_impl(context):
    """Simple test plugin."""
    return context.config


class TestConfiguration:
    """Test suite for configuration management."""

    def test_load_yaml_existing_file(self):
        """Test loading an existing YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"test": {"key": "value"}}, f)
            yaml_path = Path(f.name)

        try:
            config = load_yaml(yaml_path)
            assert config == {"test": {"key": "value"}}
        finally:
            yaml_path.unlink()

    def test_load_yaml_missing_file(self):
        """Test loading a non-existent YAML file returns empty dict."""
        config = load_yaml(Path("nonexistent.yaml"))
        assert config == {}

    def test_deep_merge_basic(self):
        """Test basic dictionary merging."""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}

        result = deep_merge(base, override)
        expected = {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
        assert result == expected

    def test_deep_merge_override(self):
        """Test that override values replace base values."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = deep_merge(base, override)
        expected = {"a": 1, "b": 3, "c": 4}
        assert result == expected

    def test_load_global_configuration_layers(self, tmp_path: Path):
        """Global config loader merges base and local layers."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        global_cfg = {"framework": {"packages": ["base"]}, "plugins": {"a": {"rows": 1}}}
        local_cfg = {"framework": {"packages": ["override"]}, "plugins": {"a": {"rows": 5}}}

        (config_dir / "global.yaml").write_text(yaml.dump(global_cfg), encoding="utf-8")
        (config_dir / "local.yaml").write_text(yaml.dump(local_cfg), encoding="utf-8")

        merged = load_global_configuration(tmp_path)

        assert merged["framework"]["packages"] == ["base", "override"]
        assert merged["plugins"]["a"]["rows"] == 5

    def test_create_configuration_context(self):
        """Test configuration context creation with hierarchy."""
        global_config = {"framework": {"name": "nexus"}, "plugins": {"test": 1}}
        case_config = {"plugins": {"test": 2, "case_only": True}}
        cli_overrides = {"plugins": {"test": 3}}
        plugin_registry = {"Test Plugin": _test_plugin_impl}

        context = create_configuration_context(
            global_config, case_config, cli_overrides, plugin_registry
        )

        # Check hierarchy: CLI > Case > Global
        assert context["plugins"]["test"] == 3  # CLI override
        assert context["plugins"]["case_only"] is True  # Case value
        assert context["framework"]["name"] == "nexus"  # Global value






