from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from nexus.contrib.repro.errors import SensorDataError
from nexus.contrib.repro.models import SensorSpec
from nexus.contrib.repro.sensors import SensorReader, SensorStore


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_matching_strategies_and_tolerance(tmp_path: Path) -> None:
    path = tmp_path / "speed.jsonl"
    write_jsonl(path, [{"timestamp_ms": 1000, "speed": 1}, {"timestamp_ms": 2000, "speed": 2}, {"timestamp_ms": 3000, "speed": 3}])
    reader = SensorReader("speed", SensorSpec(path=path, tolerance_ms=1000))
    try:
        forward = reader.match(1500)
        assert forward is not None and forward.data["speed"] == 1
        assert forward.delta_ms == -500.0

        backward = reader.match(1500, strategy="backward")
        assert backward is not None and backward.data["speed"] == 2

        nearest = reader.match(1500, strategy="nearest")
        assert nearest is not None and nearest.data["speed"] == 2

        assert reader.match(1500, tolerance_ms=100) is None
        assert reader.match(2500, strategy="nearest").data["speed"] == 3  # type: ignore[union-attr]
    finally:
        reader.close()


def test_offset_maps_raw_time_to_world_time(tmp_path: Path) -> None:
    path = tmp_path / "speed.jsonl"
    write_jsonl(path, [{"timestamp_ms": 1000, "speed": 1}, {"timestamp_ms": 2000, "speed": 2}])
    reader = SensorReader("speed", SensorSpec(path=path, offset_ms=500, tolerance_ms=0))
    try:
        match = reader.match(1500)
        assert match is not None
        assert match.raw_timestamp_ms == 1000
        assert match.world_timestamp_ms == 1500
        assert match.data["speed"] == 1
    finally:
        reader.close()


def test_empty_stream_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    reader = SensorReader("empty", SensorSpec(path=path))
    try:
        assert reader.match(1000) is None
        assert len(reader) == 0
    finally:
        reader.close()


def test_duplicate_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "dup.jsonl"
    write_jsonl(path, [{"timestamp_ms": 1000, "value": 1}, {"timestamp_ms": 1000, "value": 2}])
    reader = SensorReader("dup", SensorSpec(path=path, tolerance_ms=100))
    try:
        assert reader.match(1000, strategy="forward").data["value"] == 2  # type: ignore[union-attr]
        assert reader.match(1000, strategy="backward").data["value"] == 1  # type: ignore[union-attr]
    finally:
        reader.close()


def test_sensor_store_snapshot(tmp_path: Path) -> None:
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    write_jsonl(first, [{"timestamp_ms": 1000, "value": 1}])
    write_jsonl(second, [{"timestamp_ms": 1000, "value": 2}])
    store = SensorStore(
        {
            "a": SensorSpec(path=first, tolerance_ms=100),
            "b": SensorSpec(path=second, tolerance_ms=100),
        }
    )
    try:
        snapshot = store.snapshot(1000)
        assert snapshot["a"] is not None and snapshot["a"].data["value"] == 1
        assert snapshot["b"] is not None and snapshot["b"].data["value"] == 2
        assert store.names == ("a", "b")
        with pytest.raises(SensorDataError):
            store.match("missing", 1000)
    finally:
        store.close()


def test_invalid_sensor_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(SensorDataError):
        SensorReader("missing", SensorSpec(path=missing))

    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n", encoding="utf-8")
    with pytest.raises(SensorDataError, match="invalid JSON"):
        SensorReader("bad", SensorSpec(path=bad))

    no_timestamp = tmp_path / "no_ts.jsonl"
    no_timestamp.write_text('{"value": 1}\n', encoding="utf-8")
    with pytest.raises(SensorDataError, match="timestamp_ms"):
        SensorReader("no_ts", SensorSpec(path=no_timestamp))

    non_finite = tmp_path / "non_finite.jsonl"
    non_finite.write_text('{"timestamp_ms": NaN}\n', encoding="utf-8")
    with pytest.raises(SensorDataError, match="non-finite"):
        SensorReader("non_finite", SensorSpec(path=non_finite))
