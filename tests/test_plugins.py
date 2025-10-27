"""
Test the plugin system functionality.
"""

import pytest

from nexus.core.discovery import clear_registry, get_plugin, list_plugins, plugin
from nexus.core.types import PluginConfig


class SimpleConfig(PluginConfig):
    value: int = 42


@pytest.fixture(autouse=True)
def register_plugins():
    clear_registry()

    @plugin(name="Simple Test Plugin", config=SimpleConfig)
    def simple_test_plugin(context):  # pragma: no cover - exercised via tests
        return context.config.value * 2

    yield

    clear_registry()


class TestPluginSystem:
    def test_plugin_registration(self):
        @plugin(name="Test Registration Plugin")
        def test_plugin(context):  # pragma: no cover - simple helper
            return "test result"

        assert "Test Registration Plugin" in list_plugins()

    def test_get_plugin(self):
        spec = get_plugin("Simple Test Plugin")
        assert spec.config_model == SimpleConfig

    def test_list_plugins(self):
        plugins = list_plugins()
        assert "Simple Test Plugin" in plugins

    def test_plugin_has_config_model(self):
        assert get_plugin("Simple Test Plugin").config_model == SimpleConfig

    def test_plugin_function_callable(self):
        assert callable(get_plugin("Simple Test Plugin").func)
