from __future__ import annotations

import json
import random

import pytest

pytest.importorskip("numpy")

from nexus.contrib.repro.datagen import (
    MAX_ANGLE_H,
    MAX_ANGLE_V,
    TargetType,
    generate_adb_targets,
    generate_speed,
    generate_timeline,
    generate_timeline_from_range,
)


def test_timeline_is_deterministic_and_jittered() -> None:
    first = generate_timeline(fps=30, start_time=1000, end_time=1400, jitter_ms=2, random_seed=7)
    second = generate_timeline(fps=30, start_time=1000, end_time=1400, jitter_ms=2, random_seed=7)
    assert first == second
    assert [record["frame_index"] for record in first] == list(range(12))
    for record in first:
        expected = 1000 + record["frame_index"] * (1000 / 30)
        assert abs(record["timestamp_ms"] - expected) <= 2


def test_timeline_rejects_excessive_jitter() -> None:
    with pytest.raises(ValueError, match="jitter_ms"):
        generate_timeline(fps=30, start_time=0, end_time=1000, jitter_ms=20)


def test_timeline_from_range() -> None:
    records, start_ms, end_ms, total_frames = generate_timeline_from_range(
        start_time="2025-10-27 08:30:00",
        end_time="2025-10-27 08:30:02",
        fps=5,
        random_seed=1,
    )
    assert start_ms > 0
    assert end_ms - start_ms == pytest.approx(2000)
    assert total_frames == 10
    assert len(records) == 10


def test_timeline_from_range_keeps_exact_multiples() -> None:
    records, _, _, total_frames = generate_timeline_from_range(
        start_time="2025-10-27 08:30:00",
        end_time="2025-10-27 08:30:02",
        fps=30,
        random_seed=1,
    )
    assert total_frames == 60
    assert len(records) == 60
    assert records[-1]["frame_index"] == 59


def test_speed_is_deterministic_and_does_not_touch_global_rng() -> None:
    random.seed(1234)
    expected_global = random.random()
    random.seed(1234)
    first = generate_speed(start_time=1000, end_time=21000, random_seed=5)
    actual_global = random.random()
    second = generate_speed(start_time=1000, end_time=21000, random_seed=5)
    assert first == second
    assert actual_global == expected_global
    assert first[0]["timestamp_ms"] == pytest.approx(1000)
    assert len(first) >= 2


def test_adb_is_deterministic_and_in_fov() -> None:
    first = generate_adb_targets(
        start_time=1000, end_time=3000, frequency_hz=10, num_targets=3, random_seed=9
    )
    second = generate_adb_targets(
        start_time=1000, end_time=3000, frequency_hz=10, num_targets=3, random_seed=9
    )
    assert first == second
    assert len(first) == 20
    for frame in first:
        for target in frame["targets"]:
            assert -MAX_ANGLE_H <= target["angle_left"] <= target["angle_right"] <= MAX_ANGLE_H
            assert -MAX_ANGLE_V <= target["angle_bottom"] <= target["angle_top"] <= MAX_ANGLE_V
            assert target["distance_m"] > 0
            assert TargetType(target["type"]) in TargetType
    # JSON serialization must work even though target types are enums.
    json.dumps(first)
