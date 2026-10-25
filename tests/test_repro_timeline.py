from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("numpy")

from nexus.contrib.repro.errors import TimelineError
from nexus.contrib.repro.timeline import FramePattern, FrameTimeline


def test_frame_pattern_formats_and_matches(tmp_path: Path) -> None:
    pattern = FramePattern("frame_{:06d}.png")
    assert pattern.format(3) == "frame_000003.png"
    assert pattern.glob_pattern() == "frame_*.png"
    assert pattern.extract_index("frame_000003.png") == 3
    assert pattern.extract_index("other.png") is None

    for index in (0, 2, 10):
        (tmp_path / pattern.format(index)).write_bytes(b"x")
    assert [index for index, _path in pattern.discover(tmp_path)] == [0, 2, 10]


def test_frame_pattern_accepts_named_index(tmp_path: Path) -> None:
    pattern = FramePattern("{index:04d}.jpg")
    assert pattern.format(7) == "0007.jpg"
    (tmp_path / "0007.jpg").write_bytes(b"x")
    assert pattern.discover(tmp_path) == [(7, tmp_path / "0007.jpg")]


def test_frame_pattern_rejects_invalid_patterns() -> None:
    with pytest.raises(TimelineError):
        FramePattern("frame.png")
    with pytest.raises(TimelineError):
        FramePattern("frame_{:06d}_{:04d}.png")
    with pytest.raises(TimelineError):
        FramePattern("frame_{:x}.png")


def test_duplicate_frame_index_detected(tmp_path: Path) -> None:
    (tmp_path / "frame_1.png").write_bytes(b"x")
    (tmp_path / "frame_01.png").write_bytes(b"x")
    with pytest.raises(TimelineError, match="duplicate"):
        FramePattern("frame_{:d}.png").discover(tmp_path)


def test_timeline_csv_roundtrip(tmp_path: Path) -> None:
    timeline = FrameTimeline([0, 1, 2], [1000.0, 1033.0, 1066.0])
    path = timeline.to_csv(tmp_path / "timeline.csv")
    loaded = FrameTimeline.from_csv(path)
    assert loaded.frame_indices.tolist() == [0, 1, 2]
    assert loaded.timestamps_ms.tolist() == [1000.0, 1033.0, 1066.0]


def test_timeline_filter_and_time_range() -> None:
    timeline = FrameTimeline([10, 11, 12, 13], [1000.0, 1100.0, 1200.0, 1300.0])
    filtered = timeline.filter(start_ms=1100.0, end_ms=1200.0)
    assert filtered.frame_indices.tolist() == [11, 12]
    assert timeline.frame_range_for_time(1050.0, 1250.0) == (11, 12)
    with pytest.raises(TimelineError):
        timeline.filter(start_ms=9999.0)


def test_timeline_validation() -> None:
    with pytest.raises(TimelineError):
        FrameTimeline([], [])
    with pytest.raises(TimelineError):
        FrameTimeline([1, 0], [1000.0, 1100.0])
    # Duplicate timestamps are allowed (non-decreasing), decreasing is not.
    assert len(FrameTimeline([0, 1], [1000.0, 1000.0])) == 2
    with pytest.raises(TimelineError):
        FrameTimeline([0, 1], [1000.0, 900.0])
