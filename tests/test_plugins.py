"""
Test the plugin system functionality.

Tests demonstrate Vibecode testing principles:
- Clear, descriptive test names
- Comprehensive coverage
- Well-organized test structure
"""

import pytest
from typing import Annotated
import pandas as pd

from nexus.plugins import plugin, get_plugin, list_plugins, PLUGIN_REGISTRY
from nexus.typing import PluginConfig, DataSource, DataSink


class SimpleConfig(PluginConfig):
    """Simple configuration for testing."""
    value: int = 42


class DataConfig(PluginConfig):
    """Configuration with data sources for testing."""
    input_data: Annotated[pd.DataFrame, DataSource(name="test_data")]
    output_path: Annotated[str, DataSink(name="output_data")] = None


class TestPluginSystem:
    """Test the plugin decorator and registry."""

    def setup_method(self):
        """Clear registry before each test."""
        PLUGIN_REGISTRY.clear()

    def test_plugin_registration(self):
        """Test that plugins are registered correctly."""
        @plugin(name="Test Plugin", config=SimpleConfig)
        def test_func(config: SimpleConfig):
            return config.value * 2

        assert "Test Plugin" in PLUGIN_REGISTRY
        spec = get_plugin("Test Plugin")
        assert spec.name == "Test Plugin"
        assert spec.config_model == SimpleConfig
        assert callable(spec.func)

    def test_plugin_without_config(self):
        """Test plugin registration without configuration."""
        @plugin(name="Simple Plugin")
        def simple_func():
            return "hello"

        spec = get_plugin("Simple Plugin")
        assert spec.name == "Simple Plugin"
        assert spec.config_model is None

    def test_plugin_with_description(self):
        """Test plugin with custom description."""
        @plugin(name="Described Plugin", description="A test plugin")
        def described_func():
            return True

        spec = get_plugin("Described Plugin")
        assert spec.description == "A test plugin"

    def test_plugin_uses_docstring_as_description(self):
        """Test that plugin uses docstring when no description provided."""
        @plugin(name="Docstring Plugin")
        def docstring_func():
            """This is a docstring description."""
            return True

        spec = get_plugin("Docstring Plugin")
        assert spec.description == "This is a docstring description."

    def test_duplicate_plugin_registration_raises_error(self):
        """Test that duplicate plugin names raise an error."""
        @plugin(name="Duplicate Plugin")
        def first_func():
            return 1

        with pytest.raises(ValueError, match="Plugin 'Duplicate Plugin' is already registered"):
            @plugin(name="Duplicate Plugin")
            def second_func():
                return 2

    def test_get_nonexistent_plugin_raises_error(self):
        """Test that getting a non-existent plugin raises KeyError."""
        with pytest.raises(KeyError, match="Plugin 'Nonexistent' not found"):
            get_plugin("Nonexistent")

    def test_list_plugins(self):
        """Test listing all registered plugins."""
        @plugin(name="Plugin 1")
        def func1():
            return 1

        @plugin(name="Plugin 2")
        def func2():
            return 2

        plugins = list_plugins()
        assert len(plugins) == 2
        assert "Plugin 1" in plugins
        assert "Plugin 2" in plugins

    def test_plugin_with_data_source_annotation(self):
        """Test plugin configuration with DataSource annotation."""
        @plugin(name="Data Plugin", config=DataConfig)
        def data_func(config: DataConfig):
            return len(config.input_data)

        spec = get_plugin("Data Plugin")
        assert spec.config_model == DataConfig

        # Verify the annotation is properly set
        import typing
        hints = typing.get_type_hints(DataConfig, include_extras=True)
        assert 'input_data' in hints
        assert 'output_path' in hints