"""
Test the plugin system functionality.

Tests demonstrate simplified plugin registration and execution.
"""

import pandas as pd

from nexus.core.discovery import PLUGIN_REGISTRY, get_plugin, list_plugins, plugin
from nexus.core.types import PluginConfig


class SimpleConfig(PluginConfig):
    """Simple configuration for testing."""

    value: int = 42


@plugin(name="Simple Test Plugin", config=SimpleConfig)
def simple_test_plugin(context):
    """Simple test plugin function."""
    return context.config.value * 2


class TestPluginSystem:
    """Test suite for plugin functionality."""

    def test_plugin_registration(self):
        """Test that plugins can be registered."""

        @plugin(name="Test Registration Plugin")
        def test_plugin(context):
            return "test result"

        assert "Test Registration Plugin" in PLUGIN_REGISTRY

    def test_get_plugin(self):
        """Test retrieving a registered plugin."""
        spec = get_plugin("Simple Test Plugin")
        assert spec is not None
        assert spec.func == simple_test_plugin

    def test_list_plugins(self):
        """Test listing all registered plugins."""
        plugins = list_plugins()
        assert isinstance(plugins, dict)
        assert "Simple Test Plugin" in plugins

    def test_plugin_has_config_model(self):
        """Test that plugin has correct configuration model."""
        spec = get_plugin("Simple Test Plugin")
        assert spec.config_model == SimpleConfig

    def test_plugin_function_callable(self):
        """Test that plugin function is callable."""
        spec = get_plugin("Simple Test Plugin")
        assert callable(spec.func)
