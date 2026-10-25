"""Frame timelines and frame filename patterns."""

from __future__ import annotations

import csv
import re
import string
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .errors import TimelineError

TIMELINE_COLUMNS = ("frame_index", "timestamp_ms")
_FIELD_NAMES = {"", "index", "frame_index"}


@dataclass(frozen=True)
class FramePattern:
    """A validated frame filename pattern such as ``frame_{:06d}.png``."""

    pattern: str
    _parsed: list = field(init=False, repr=False, compare=False)
    _format_spec: str = field(init=False, repr=False, compare=False)
    _glob: str = field(init=False, repr=False, compare=False)
    _regex: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        parsed = list(string.Formatter().parse(self.pattern))
        fields = [item for item in parsed if item[1] is not None]
        if len(fields) != 1:
            raise TimelineError(
                f"frame pattern must contain exactly one replacement field, got {len(fields)}: {self.pattern!r}"
            )
        _, field_name, format_spec, conversion = fields[0]
        if field_name not in _FIELD_NAMES:
            raise TimelineError(
                f"frame pattern field must be empty, 'index' or 'frame_index', got {field_name!r}"
            )
        if conversion:
            raise TimelineError(f"frame pattern conversion is not supported: {self.pattern!r}")
        if format_spec and not re.fullmatch(r"0?\d*d", format_spec):
            raise TimelineError(
                f"frame pattern format spec must be a decimal integer spec such as '06d', got {format_spec!r}"
            )
        object.__setattr__(self, "_parsed", parsed)
        object.__setattr__(self, "_format_spec", format_spec or "d")
        literal_parts: list[str] = []
        for literal, field_name, _format_spec, _conversion in parsed:
            literal_parts.append(literal)
            if field_name is not None:
                literal_parts.append("*")
        object.__setattr__(self, "_glob", "".join(literal_parts))
        regex_parts: list[str] = []
        for literal, field_name, _format_spec, _conversion in parsed:
            regex_parts.append(re.escape(literal))
            if field_name is not None:
                regex_parts.append(r"(?P<index>\d+)")
        object.__setattr__(self, "_regex", re.compile("".join(regex_parts) + r"\Z"))

    def format(self, index: int) -> str:
        parts: list[str] = []
        for literal, field_name, _format_spec, _conversion in self._parsed:
            parts.append(literal)
            if field_name is not None:
                parts.append(format(index, self._format_spec))
        return "".join(parts)

    def path_for(self, directory: Path | str, index: int) -> Path:
        return Path(directory) / self.format(index)

    def glob_pattern(self) -> str:
        return self._glob

    def extract_index(self, name: str) -> int | None:
        match = self._regex.fullmatch(name)
        return int(match.group("index")) if match else None

    def discover(self, directory: Path | str) -> list[tuple[int, Path]]:
        directory = Path(directory)
        if not directory.exists():
            raise TimelineError(f"frame directory not found: {directory}")
        found: dict[int, Path] = {}
        for path in sorted(directory.glob(self._glob)):
            if not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            index = self.extract_index(relative)
            if index is None:
                continue
            if index in found:
                raise TimelineError(
                    f"duplicate frame index {index} in {directory}: {found[index].name} and {path.name}"
                )
            found[index] = path
        return sorted(found.items())

    def __str__(self) -> str:
        return self.pattern


class FrameTimeline:
    """Sorted frame indices and their absolute timestamps in milliseconds."""

    def __init__(self, frame_indices: Sequence[int] | np.ndarray, timestamps_ms: Sequence[float] | np.ndarray):
        indices = np.asarray(frame_indices, dtype=np.int64)
        timestamps = np.asarray(timestamps_ms, dtype=np.float64)
        if indices.ndim != 1 or timestamps.ndim != 1:
            raise TimelineError("frame indices and timestamps must be one-dimensional")
        if len(indices) != len(timestamps):
            raise TimelineError(
                f"timeline length mismatch: {len(indices)} frame indices, {len(timestamps)} timestamps"
            )
        if len(indices) == 0:
            raise TimelineError("timeline must contain at least one frame")
        if np.any(indices < 0):
            raise TimelineError("frame indices must be non-negative")
        if not np.all(np.diff(indices) > 0):
            raise TimelineError("frame indices must be strictly increasing")
        if not np.all(np.isfinite(timestamps)):
            raise TimelineError("timestamps must be finite")
        if not np.all(np.diff(timestamps) >= 0):
            raise TimelineError("frame timestamps must be non-decreasing")
        self.frame_indices = indices
        self.timestamps_ms = timestamps

    def __len__(self) -> int:
        return len(self.frame_indices)

    def __iter__(self) -> Iterator[tuple[int, float]]:
        return iter(zip(self.frame_indices.tolist(), self.timestamps_ms.tolist(), strict=True))

    @classmethod
    def from_records(cls, records: Iterable[dict[str, Any]]) -> FrameTimeline:
        indices: list[int] = []
        timestamps: list[float] = []
        for record in records:
            try:
                indices.append(int(record["frame_index"]))
                timestamps.append(float(record["timestamp_ms"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise TimelineError(f"invalid timeline record: {record!r}") from exc
        return cls(indices, timestamps)

    @classmethod
    def from_csv(cls, path: Path | str) -> FrameTimeline:
        path = Path(path)
        if not path.exists():
            raise TimelineError(f"timeline not found: {path}")
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    raise TimelineError(f"timeline has no header: {path}")
                missing = [column for column in TIMELINE_COLUMNS if column not in reader.fieldnames]
                if missing:
                    raise TimelineError(
                        f"timeline {path} is missing columns {missing}; expected {list(TIMELINE_COLUMNS)}"
                    )
                records = list(reader)
        except OSError as exc:
            raise TimelineError(f"cannot read timeline {path}: {exc}") from exc
        return cls.from_records(records)

    def to_records(self) -> list[dict[str, Any]]:
        return [
            {"frame_index": int(index), "timestamp_ms": float(timestamp)}
            for index, timestamp in zip(self.frame_indices, self.timestamps_ms, strict=True)
        ]

    def to_csv(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(TIMELINE_COLUMNS))
            writer.writeheader()
            writer.writerows(self.to_records())
        return path

    def filter(
        self,
        *,
        start_ms: float | None = None,
        end_ms: float | None = None,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> FrameTimeline:
        mask = np.ones(len(self), dtype=bool)
        if start_ms is not None:
            mask &= self.timestamps_ms >= start_ms
        if end_ms is not None:
            mask &= self.timestamps_ms <= end_ms
        if start_frame is not None:
            mask &= self.frame_indices >= start_frame
        if end_frame is not None:
            mask &= self.frame_indices <= end_frame
        if not np.any(mask):
            raise TimelineError("timeline selection is empty")
        return FrameTimeline(self.frame_indices[mask], self.timestamps_ms[mask])

    def frame_range_for_time(self, start_ms: float | None, end_ms: float | None) -> tuple[int | None, int | None]:
        """Map a time range to the first/last frame indices present in it."""

        start_frame: int | None = None
        end_frame: int | None = None
        if start_ms is not None:
            position = int(np.searchsorted(self.timestamps_ms, start_ms, side="left"))
            if position >= len(self):
                raise TimelineError(f"start_ms {start_ms} is after the last frame")
            start_frame = int(self.frame_indices[position])
        if end_ms is not None:
            position = int(np.searchsorted(self.timestamps_ms, end_ms, side="right")) - 1
            if position < 0:
                raise TimelineError(f"end_ms {end_ms} is before the first frame")
            end_frame = int(self.frame_indices[position])
        if start_frame is not None and end_frame is not None and start_frame > end_frame:
            raise TimelineError(f"time range selects no frames: {start_ms}..{end_ms}")
        return start_frame, end_frame
