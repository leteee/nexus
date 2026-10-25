from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("cv2")
pytest.importorskip("numpy")
pytest.importorskip("tqdm")

from nexus.contrib.repro import probe_video
from nexus.core.config import EngineSettings
from nexus.core.engine import Engine
from nexus.core.models import RunStatus


def test_repro_pipeline(tmp_path: Path, project_root: Path) -> None:
    settings = EngineSettings(
        project_root=project_root,
        node_modules=["nexus.contrib.repro.nodes"],
        load_entry_points=False,
    )
    engine = Engine(settings=settings)

    datagen = engine.run(
        project_root / "flows" / "repro" / "repro_datagen.yaml",
        workdir=tmp_path,
        variables={
            "fps": 5.0,
            "width": 320,
            "height": 240,
            "start_time": "2025-10-27 08:30:00",
            "end_time": "2025-10-27 08:30:01",
        },
    )
    assert datagen.status is RunStatus.SUCCESS, datagen.error
    assert datagen.steps["video"].use == "repro.datagen.video"
    input_video = tmp_path / "input" / "synthetic_driving.mp4"
    assert input_video.exists()
    assert (tmp_path / "temp" / "timeline.csv").exists()
    input_probe = probe_video(input_video)
    assert (input_probe.width, input_probe.height) == (320, 240)
    assert input_probe.total_frames == 5

    replay = engine.run(
        project_root / "flows" / "repro" / "repro.yaml",
        workdir=tmp_path,
        variables={
            "start_time": "2025-10-27 08:30:00.0",
            "end_time": "2025-10-27 08:30:00.8",
            "workers": 2,
            "camera": str(project_root / "tests" / "fixtures" / "camera_320x240.json"),
        },
    )
    assert replay.status is RunStatus.SUCCESS, replay.error
    assert replay.steps["render"].use == "repro.render.frames"
    assert replay.steps["render"].outputs["rendered_count"] >= 1
    output_video = tmp_path / "output" / "repro.mp4"
    assert output_video.exists()
    probe = probe_video(output_video)
    assert (probe.width, probe.height) == (320, 240)
    assert probe.fps == pytest.approx(5.0)
    assert probe.total_frames == 5
