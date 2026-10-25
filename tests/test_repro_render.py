from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("cv2")

import cv2
import numpy as np

from nexus.contrib.repro.errors import MissingFrameError, OutputExistsError, RendererError
from nexus.contrib.repro.models import RendererSpec, RenderRequest, SensorSpec
from nexus.contrib.repro.render import ReplayPipeline
from nexus.contrib.repro.timeline import FrameTimeline

PATTERN = "frame_{:06d}.png"


def prepare(tmp_path: Path, count: int = 3) -> tuple[Path, Path, Path]:
    frames = tmp_path / "frames"
    frames.mkdir()
    for index in range(count):
        frame = np.full((48, 64, 3), (20 + index * 10, 60, 90), dtype=np.uint8)
        cv2.imwrite(str(frames / PATTERN.format(index)), frame)
    timeline = FrameTimeline(list(range(count)), [1000.0 + index * 100 for index in range(count)])
    timeline_path = timeline.to_csv(tmp_path / "timeline.csv")
    sensor = tmp_path / "speed.jsonl"
    sensor.write_text(
        "\n".join(
            json.dumps({"timestamp_ms": 1000.0 + index * 100, "speed": 10.0 + index})
            for index in range(count)
        )
        + "\n",
        encoding="utf-8",
    )
    return frames, timeline_path, sensor


def request(
    tmp_path: Path,
    frames: Path,
    timeline: Path,
    sensor: Path,
    *,
    output: str = "out",
    workers: int = 1,
    overwrite: bool = False,
    missing_frame: str = "fail",
    start_ms: float | None = None,
    end_ms: float | None = None,
    renderer_type: str = "speed",
) -> RenderRequest:
    return RenderRequest(
        frames_dir=frames,
        timeline=timeline,
        output_dir=tmp_path / output,
        sensors={"speed": SensorSpec(path=sensor, tolerance_ms=100, strategy="nearest")},
        renderers=[
            RendererSpec(
                type=renderer_type,
                sensors={"speed": "speed"},
                config={
                    "style": {
                        "font": {"scale": 0.4},
                        "position": {"x": 2, "y": 12},
                    }
                },
            )
        ],
        start_ms=start_ms,
        end_ms=end_ms,
        workers=workers,
        overwrite=overwrite,
        missing_frame=missing_frame,  # type: ignore[arg-type]
        progress=False,
    )


def test_render_is_deterministic_across_workers(tmp_path: Path) -> None:
    frames, timeline, sensor = prepare(tmp_path)
    first = ReplayPipeline().render(request(tmp_path, frames, timeline, sensor, output="one", workers=1))
    second = ReplayPipeline().render(request(tmp_path, frames, timeline, sensor, output="two", workers=3))
    assert first.rendered_count == 3
    assert second.rendered_count == 3
    for index in range(3):
        name = PATTERN.format(index)
        assert (first.output_dir / name).read_bytes() == (second.output_dir / name).read_bytes()


def test_overwrite_is_explicit(tmp_path: Path) -> None:
    frames, timeline, sensor = prepare(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(OutputExistsError):
        ReplayPipeline().render(request(tmp_path, frames, timeline, sensor))
    assert marker.exists()

    result = ReplayPipeline().render(request(tmp_path, frames, timeline, sensor, overwrite=True))
    assert result.rendered_count == 3
    assert not marker.exists()
    assert (output / PATTERN.format(0)).exists()


def test_missing_frame_fail_or_skip(tmp_path: Path) -> None:
    frames, timeline, sensor = prepare(tmp_path, count=1)
    timeline_path = FrameTimeline([0, 5], [1000.0, 1500.0]).to_csv(tmp_path / "long.csv")
    with pytest.raises(MissingFrameError):
        ReplayPipeline().render(request(tmp_path, frames, timeline_path, sensor, output="fail", missing_frame="fail"))
    result = ReplayPipeline().render(
        request(tmp_path, frames, timeline_path, sensor, output="skip", missing_frame="skip")
    )
    assert result.rendered_count == 1
    assert result.skipped_count == 1


def test_time_filter(tmp_path: Path) -> None:
    frames, timeline, sensor = prepare(tmp_path)
    result = ReplayPipeline().render(
        request(tmp_path, frames, timeline, sensor, start_ms=1100.0, end_ms=1200.0)
    )
    assert result.frame_count == 2
    assert sorted(path.name for path in result.output_dir.glob("*.png")) == [
        PATTERN.format(1),
        PATTERN.format(2),
    ]


def test_unknown_renderer_or_sensor(tmp_path: Path) -> None:
    frames, timeline, sensor = prepare(tmp_path)
    with pytest.raises(RendererError):
        ReplayPipeline().render(request(tmp_path, frames, timeline, sensor, renderer_type="nope"))
    bad = request(tmp_path, frames, timeline, sensor)
    bad.sensors = {}
    with pytest.raises(RendererError):
        ReplayPipeline().render(bad)


def test_frame_info_renderer(tmp_path: Path) -> None:
    frames, timeline, _sensor = prepare(tmp_path)
    result = ReplayPipeline().render(
        RenderRequest(
            frames_dir=frames,
            timeline=timeline,
            output_dir=tmp_path / "info",
            sensors={},
            renderers=[RendererSpec(type="frame_info", config={"format": "compact"})],
            progress=False,
        )
    )
    assert result.rendered_count == 3


def test_blank_frames_and_compose(tmp_path: Path) -> None:
    from nexus.contrib.repro.timeline import FrameTimeline
    from nexus.contrib.repro.video import blank_frames, compose_video

    timeline = FrameTimeline([0, 1, 2], [1000.0, 1100.0, 1200.0])
    frames = blank_frames(
        timeline,
        tmp_path / "blank",
        width=64,
        height=48,
        frame_pattern=PATTERN,
        progress=False,
    )
    assert frames.frame_count == 3
    result = compose_video(
        tmp_path / "blank",
        tmp_path / "blank.mp4",
        fps=10,
        frame_pattern=PATTERN,
        progress=False,
    )
    assert result.frame_count == 3
    assert (tmp_path / "blank.mp4").exists()
