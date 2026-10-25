"""Indexed sensor streams and time-based matching."""

from __future__ import annotations

import contextlib
import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from .errors import SensorDataError
from .models import MatchStrategy, SensorMatch, SensorSpec


class SensorReader:
    """JSONL sensor stream backed by a timestamp/offset index.

    The file is scanned once to collect timestamps and byte offsets.  Record
    bodies are read on demand with ``os.pread``, so memory usage is proportional
    to the number of records rather than the size of their JSON payloads.
    """

    def __init__(self, name: str, spec: SensorSpec) -> None:
        self.name = name
        self.spec = spec
        self.path = Path(os.path.expandvars(str(spec.path))).expanduser()
        self.offset_ms = float(spec.offset_ms)
        self.tolerance_ms = float(spec.tolerance_ms)
        if not math.isfinite(self.offset_ms):
            raise SensorDataError(f"sensor '{name}' offset_ms must be finite")
        self.strategy: MatchStrategy = spec.strategy
        self._fd: int | None = None
        self._offsets = np.empty(0, dtype=np.int64)
        self._lengths = np.empty(0, dtype=np.int64)
        self._world_timestamps = np.empty(0, dtype=np.float64)
        self._load()

    # -- lifecycle --------------------------------------------------------

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> SensorReader:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - defensive cleanup
        with contextlib.suppress(Exception):
            self.close()

    # -- loading ----------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            raise SensorDataError(f"sensor '{self.name}' file not found: {self.path}")
        offsets: list[int] = []
        lengths: list[int] = []
        timestamps: list[float] = []
        try:
            with self.path.open("rb") as handle:
                line_number = 0
                while True:
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    line_number += 1
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise SensorDataError(
                            f"sensor '{self.name}' has invalid JSON at line {line_number}: {exc}"
                        ) from exc
                    if not isinstance(record, dict):
                        raise SensorDataError(
                            f"sensor '{self.name}' line {line_number} must be a JSON object"
                        )
                    if "timestamp_ms" not in record:
                        raise SensorDataError(
                            f"sensor '{self.name}' line {line_number} is missing 'timestamp_ms'"
                        )
                    try:
                        timestamp = float(record["timestamp_ms"])
                    except (TypeError, ValueError) as exc:
                        raise SensorDataError(
                            f"sensor '{self.name}' line {line_number} has a non-numeric timestamp"
                        ) from exc
                    if not math.isfinite(timestamp):
                        raise SensorDataError(
                            f"sensor '{self.name}' line {line_number} has a non-finite timestamp"
                        )
                    offsets.append(offset)
                    lengths.append(len(line))
                    timestamps.append(timestamp)
        except OSError as exc:
            raise SensorDataError(f"cannot read sensor '{self.name}' at {self.path}: {exc}") from exc

        raw = np.asarray(timestamps, dtype=np.float64)
        order = np.argsort(raw + self.offset_ms, kind="stable")
        self._offsets = np.asarray(offsets, dtype=np.int64)[order]
        self._lengths = np.asarray(lengths, dtype=np.int64)[order]
        self._world_timestamps = (raw + self.offset_ms)[order]
        self._fd = os.open(self.path, os.O_RDONLY)

    # -- matching ---------------------------------------------------------

    def _read_record(self, index: int) -> dict[str, Any]:
        if self._fd is None:
            raise SensorDataError(f"sensor '{self.name}' is closed")
        offset = int(self._offsets[index])
        length = int(self._lengths[index])
        try:
            raw = os.pread(self._fd, length, offset)
        except OSError as exc:
            raise SensorDataError(f"cannot read sensor '{self.name}' record {index}: {exc}") from exc
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SensorDataError(f"sensor '{self.name}' record {index} is invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise SensorDataError(f"sensor '{self.name}' record {index} is not an object")
        return record

    def _find_index(self, snapshot_ms: float, strategy: MatchStrategy) -> int | None:
        if len(self._world_timestamps) == 0:
            return None
        if strategy == "forward":
            position = int(np.searchsorted(self._world_timestamps, snapshot_ms, side="right")) - 1
            return position if position >= 0 else None
        if strategy == "backward":
            position = int(np.searchsorted(self._world_timestamps, snapshot_ms, side="left"))
            return position if position < len(self._world_timestamps) else None
        if strategy == "nearest":
            position = int(np.searchsorted(self._world_timestamps, snapshot_ms, side="left"))
            if position == 0:
                return 0
            if position >= len(self._world_timestamps):
                return len(self._world_timestamps) - 1
            before = self._world_timestamps[position - 1]
            after = self._world_timestamps[position]
            return position - 1 if (snapshot_ms - before) < (after - snapshot_ms) else position
        raise SensorDataError(f"unsupported matching strategy '{strategy}'")

    def match(
        self,
        snapshot_ms: float,
        *,
        strategy: MatchStrategy | None = None,
        tolerance_ms: float | None = None,
    ) -> SensorMatch | None:
        effective_strategy = strategy or self.strategy
        effective_tolerance = self.tolerance_ms if tolerance_ms is None else float(tolerance_ms)
        index = self._find_index(snapshot_ms, effective_strategy)
        if index is None:
            return None
        world_timestamp = float(self._world_timestamps[index])
        delta = world_timestamp - snapshot_ms
        if abs(delta) > effective_tolerance:
            return None
        return SensorMatch(
            sensor=self.name,
            raw_timestamp_ms=world_timestamp - self.offset_ms,
            world_timestamp_ms=world_timestamp,
            snapshot_ms=snapshot_ms,
            delta_ms=delta,
            strategy=effective_strategy,
            tolerance_ms=effective_tolerance,
            data=self._read_record(index),
        )

    def __len__(self) -> int:
        return len(self._world_timestamps)

    @property
    def world_timestamps(self) -> np.ndarray:
        return self._world_timestamps


class SensorStore:
    """Named collection of :class:`SensorReader` objects."""

    def __init__(self, specs: Mapping[str, SensorSpec]) -> None:
        self._readers: dict[str, SensorReader] = {}
        try:
            for name, spec in specs.items():
                if not name:
                    raise SensorDataError("sensor name must not be empty")
                self._readers[name] = SensorReader(name, spec)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        for reader in self._readers.values():
            reader.close()

    def __enter__(self) -> SensorStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def match(self, name: str, snapshot_ms: float, *, strategy: MatchStrategy | None = None) -> SensorMatch | None:
        reader = self._readers.get(name)
        if reader is None:
            raise SensorDataError(f"sensor '{name}' is not registered")
        return reader.match(snapshot_ms, strategy=strategy)

    def snapshot(self, snapshot_ms: float) -> dict[str, SensorMatch | None]:
        return {name: reader.match(snapshot_ms) for name, reader in self._readers.items()}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._readers)

    @property
    def readers(self) -> Mapping[str, SensorReader]:
        return dict(self._readers)

    def __len__(self) -> int:
        return len(self._readers)
