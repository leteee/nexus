"""
Tests for the simplified PipelineEngine.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from nexus.core.discovery import clear_registry, plugin
from nexus.core.engine import PipelineEngine


def _register_stubs():
    clear_registry()

    @plugin(name="Stub Generator")
    def stub_generator(ctx):  # pragma: no cover - test helper
        frame = {"rows": list(range(5))}
        ctx.remember("last_result", frame)
        return frame

    @plugin(name="Stub Transformer")
    def stub_transformer(ctx):  # pragma: no cover - test helper
        data = ctx.recall("last_result", {})
        data = {"rows": [value * 2 for value in data.get("rows", [])]}
        ctx.remember("last_result", data)
        return data


@pytest.fixture(autouse=True)
def reset_registry():
    _register_stubs()
    yield
    clear_registry()


class TestPipelineEngine:
    def test_run_pipeline_shared_state(self, tmp_path: Path):
        project_root = tmp_path
        case_dir = project_root / "cases" / "demo"
        case_dir.mkdir(parents=True)

        engine = PipelineEngine(project_root, case_dir)

        pipeline_config = {
            "pipeline": [
                {"plugin": "Stub Generator"},
                {"plugin": "Stub Transformer"},
            ]
        }

        results = engine.run_pipeline(pipeline_config)

        assert "step_1_result" in results
        assert "step_2_result" in results
        assert results["step_2_result"]["rows"] == [0, 2, 4, 6, 8]

    def test_run_single_plugin(self, tmp_path: Path):
        project_root = tmp_path
        case_dir = project_root / "cases" / "demo"
        case_dir.mkdir(parents=True)

        engine = PipelineEngine(project_root, case_dir)
        result = engine.run_single_plugin("Stub Generator")

        assert result["rows"] == list(range(5))

    def test_missing_step_plugin(self, tmp_path: Path):
        project_root = tmp_path
        case_dir = project_root / "cases" / "demo"
        case_dir.mkdir(parents=True)

        engine = PipelineEngine(project_root, case_dir)

        pipeline_config = {"pipeline": [{"config": {}}]}

        with pytest.raises(ValueError):
            engine.run_pipeline(pipeline_config)

    def test_missing_pipeline_definition(self, tmp_path: Path):
        project_root = tmp_path
        case_dir = project_root / "cases" / "demo"
        case_dir.mkdir(parents=True)

        engine = PipelineEngine(project_root, case_dir)

        with pytest.raises(ValueError):
            engine.run_pipeline({})
