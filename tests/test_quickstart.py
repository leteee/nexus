from __future__ import annotations

import json
from pathlib import Path

from nexus.core.config import EngineSettings
from nexus.core.engine import Engine
from nexus.core.models import RunStatus


def test_quickstart_uses_only_core_and_io(tmp_path: Path, project_root: Path) -> None:
    settings = EngineSettings(project_root=project_root, load_entry_points=False)
    engine = Engine(settings=settings)
    result = engine.run(project_root / "flows" / "quickstart.yaml", workdir=tmp_path)
    assert result.status is RunStatus.SUCCESS, result.error
    assert set(result.steps) == {"seed", "load", "count", "check", "report"}
    assert result.outputs["count"] == 3

    report_path = tmp_path / "data" / "report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["count"] == 3
    assert len(report["rows"]) == 3
    assert report["source"] == "data/people.json"


def test_basic_pack_is_gone() -> None:
    import importlib.util

    assert importlib.util.find_spec("nexus.contrib.basic") is None
