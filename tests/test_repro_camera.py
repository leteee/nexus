from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("cv2")

import numpy as np

from nexus.contrib.repro.camera import DEFAULT_CAMERA_PATH, CameraModel
from nexus.contrib.repro.errors import ReproError
from nexus.contrib.repro.renderers import RenderContext, TargetRenderer
from nexus.contrib.repro.renderers.targets import TargetConfig


def identity_camera() -> CameraModel:
    return CameraModel(
        [[100, 0, 50], [0, 100, 50], [0, 0, 1]],
        [0, 0, 0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
        image_width=100,
        image_height=100,
    )


def test_project_points() -> None:
    camera = identity_camera()
    projected = camera.project(np.array([[1.0, 2.0, 10.0]], dtype=np.float32))
    assert projected.shape == (1, 2)
    assert projected[0].tolist() == pytest.approx([60.0, 70.0])


def test_frame_size_must_match_calibration() -> None:
    camera = identity_camera()
    camera.validate_frame_size(100, 100)
    with pytest.raises(ReproError, match="100x100"):
        camera.validate_frame_size(200, 100)

    default = CameraModel.load()
    default.validate_frame_size(1920, 1080)
    with pytest.raises(ReproError, match="1920x1080"):
        default.validate_frame_size(320, 240)

    fixture = CameraModel.from_file(Path(__file__).parent / "fixtures" / "camera_320x240.json")
    fixture.validate_frame_size(320, 240)


def test_default_calibration_and_target_projection() -> None:
    assert DEFAULT_CAMERA_PATH.exists()
    camera = CameraModel.load()
    target = {
        "id": 1,
        "type": "car",
        "distance_m": 30.0,
        "angle_left": -2.0,
        "angle_right": 2.0,
        "angle_top": 0.5,
        "angle_bottom": -0.5,
    }
    projected = camera.project_target_box(target)
    assert projected is not None
    assert len(projected.corners) == 4
    assert set(projected.ads_bounds) == {"x_left", "x_right", "y_top", "y_bottom"}


def test_invalid_calibration() -> None:
    with pytest.raises(ReproError):
        CameraModel([[1, 0], [0, 1]], [0], [0, 0, 0], [0, 0, 0])
    with pytest.raises(ReproError):
        CameraModel.from_dict({"camera_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]})


def test_target_renderer_rejects_resolution_mismatch() -> None:
    renderer = TargetRenderer(TargetConfig(camera="auto"))
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    context = RenderContext(frame_index=0, timestamp_ms=0.0)
    with pytest.raises(ReproError, match="320x240"):
        renderer.render(frame, context)
