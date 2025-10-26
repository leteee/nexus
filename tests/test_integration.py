"""
End-to-end integration tests for the Nexus framework.
"""

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from nexus.core.discovery import clear_registry, plugin
from nexus.core.engine import PipelineEngine
from nexus.core.types import PluginConfig


class _TestDataProcessorConfig(PluginConfig):
    multiplier: int = 2


def _register_integration_plugin():
    clear_registry()

    @plugin(name="Test Data Processor", config=_TestDataProcessorConfig)
    def _impl(ctx):  # pragma: no cover - exercised via tests
        return pd.DataFrame(
            {
                "id": [1, 2, 3],
                "value": [10, 20, 30],
            }
        ) * ctx.config.multiplier


@pytest.fixture(autouse=True)
def integration_plugins():
    _register_integration_plugin()
    yield
    clear_registry()


class TestIntegration:
    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "project"
        self.case_dir = self.project_root / "cases" / "demo"

        self.project_root.mkdir(parents=True)
        self.case_dir.mkdir(parents=True)

        config_dir = self.project_root / "config"
        config_dir.mkdir()
        (config_dir / "global.yaml").write_text(
            "framework:\n  cases_roots:\n    - \"cases\"\n  templates_roots:\n    - \"templates\"\n  packages: []\n"
        )

        (self.project_root / "templates").mkdir()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_pipeline_engine_creation(self):
        engine = PipelineEngine(self.project_root, self.case_dir)
        assert engine.project_root == self.project_root
        assert engine.case_dir == self.case_dir

    def test_basic_plugin_execution(self):
        engine = PipelineEngine(self.project_root, self.case_dir)
        result = engine.run_single_plugin("Test Data Processor", {"multiplier": 3})

        assert isinstance(result, pd.DataFrame)
        assert result["value"].tolist() == [30, 60, 90]
