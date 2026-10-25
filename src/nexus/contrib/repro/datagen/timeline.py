"""Timeline generation with realistic capture jitter."""

from __future__ import annotations

import csv
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from ..time import parse_timestamp


def generate_timeline(
    *,
    fps: float,
    start_time: float,
    end_time: float,
    jitter_ms: int = 2,
    random_seed: int | None = None,
) -> list[dict[str, Any]]:
    """Generate frame indices between two absolute millisecond timestamps.

    ``end_time`` is exclusive for frame-count purposes:
    ``total_frames = int((end_time - start_time) * fps / 1000)``.
    A tiny epsilon keeps exact multiples (for example 2s at 30fps = 60)
    from truncating to 59 due to floating-point error.
    """

    if fps <= 0:
        raise ValueError("fps must be positive")
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")
    if jitter_ms < 0:
        raise ValueError("jitter_ms must be >= 0")

    frame_duration_ms = 1000.0 / fps
    if jitter_ms * 2 >= frame_duration_ms:
        raise ValueError("jitter_ms must be smaller than half a frame duration")

    total_frames = int((end_time - start_time) / frame_duration_ms + 1e-9)
    if total_frames < 1:
        raise ValueError("time range is too short for the requested fps")

    rng = random.Random(random_seed)
    timeline: list[dict[str, Any]] = []
    for frame_index in range(total_frames):
        ideal = start_time + frame_index * frame_duration_ms
        # Pin the first frame to the requested start to keep time-range filtering
        # inclusive; interior frames still carry realistic jitter.
        jitter = 0 if frame_index == 0 else rng.randint(-jitter_ms, jitter_ms)
        timestamp = min(ideal + jitter, end_time)
        timeline.append({"frame_index": frame_index, "timestamp_ms": timestamp})
    return timeline


def generate_timeline_from_range(
    *,
    start_time: str | datetime | float,
    end_time: str | datetime | float,
    fps: float,
    jitter_ms: int = 0,
    random_seed: int | None = None,
) -> tuple[list[dict[str, Any]], float, float, int]:
    """Build a timeline from string/datetime/ms bounds.

    Returns ``(records, start_timestamp_ms, end_timestamp_ms, total_frames)``.
    """

    start_ms = float(parse_timestamp(start_time))
    end_ms = float(parse_timestamp(end_time))
    records = generate_timeline(
        fps=fps,
        start_time=start_ms,
        end_time=end_ms,
        jitter_ms=jitter_ms,
        random_seed=random_seed,
    )
    return records, start_ms, end_ms, len(records)


def save_timeline_csv(records: list[dict[str, Any]], output_path: Path | str) -> Path:
    """Write timeline records to CSV without pandas."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frame_index", "timestamp_ms"])
        writer.writeheader()
        writer.writerows(records)
    return output_path
