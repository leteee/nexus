"""
Type definitions for data replay system.

Defines data structures for frame timing, data points, and rendering protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import numpy as np
import pandas as pd


@dataclass
class FrameTimestamp:
    """Maps frame index to physical timestamp."""

    frame_index: int
    timestamp_ms: float


@dataclass
class DataPoint:
    """Represents a single timestamped data point."""

    timestamp_ms: float
    data: dict[str, Any]  # Flexible data payload (supports nested structures)


@dataclass
class VideoMetadata:
    """Metadata about extracted video frames."""

    total_frames: int
    fps: float
    width: int
    height: int
    output_dir: Path


class DataRenderer(ABC):
    """
    Abstract base class for rendering time-series data onto video frames.

    Users implement this class to define custom data visualizations.

    Required implementations:
        1. load_data() - How to load data from file (JSONL/CSV/etc)
        2. match_data() - How to find data matching a timestamp
        3. render() - How to draw data on frame

    Example:
        >>> class SpeedRenderer(DataRenderer):
        ...     def load_data(self, data_path):
        ...         self.data = load_jsonl(data_path)
        ...
        ...     def match_data(self, timestamp_ms):
        ...         # Find nearest data point
        ...         ...
        ...
        ...     def render(self, frame, data):
        ...         # Draw speed on frame
        ...         cv2.putText(frame, f"Speed: {data['speed']}", ...)
        ...         return frame
    """

    def __init__(self, data_path: Path | str):
        """
        Initialize renderer with data source.

        Args:
            data_path: Path to data file (JSONL, CSV, etc.)
        """
        self.data_path = Path(data_path)
        self.data = None
        self.load_data(self.data_path)

    @abstractmethod
    def load_data(self, data_path: Path) -> None:
        """
        Load time-series data from file.

        Must set self.data to loaded dataset.
        Supports JSONL (recommended), CSV, or custom formats.

        Args:
            data_path: Path to data file

        Example:
            >>> def load_data(self, data_path):
            ...     self.data = load_jsonl(data_path)
        """
        raise NotImplementedError

    @abstractmethod
    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """
        Find data points matching the given timestamp.

        Args:
            timestamp_ms: Target timestamp in milliseconds
            tolerance_ms: Maximum acceptable time difference

        Returns:
            List of matching data dictionaries

        Example:
            >>> def match_data(self, timestamp_ms, tolerance_ms=50.0):
            ...     matches = [d for d in self.data
            ...                if abs(d['timestamp_ms'] - timestamp_ms) <= tolerance_ms]
            ...     return matches[:1]  # Return nearest
        """
        raise NotImplementedError

    @abstractmethod
    def render(
        self,
        frame: np.ndarray,
        data: List[dict],
    ) -> np.ndarray:
        """
        Render data visualization onto frame.

        Args:
            frame: Video frame as numpy array (H, W, C) in BGR format
            data: Matched data points to visualize

        Returns:
            Frame with data rendered (modified in-place or copied)

        Example:
            >>> def render(self, frame, data):
            ...     if not data:
            ...         return frame
            ...     speed = data[0].get('speed', 0)
            ...     cv2.putText(frame, f"Speed: {speed:.1f}", (20, 50), ...)
            ...     return frame
        """
        raise NotImplementedError


def load_frame_timestamps(csv_path: Path) -> pd.DataFrame:
    """
    Load frame-to-timestamp mapping from CSV.

    Expected CSV format:
        frame_index,timestamp_ms
        0,0.0
        1,33.33
        2,66.67

    Args:
        csv_path: Path to frame timestamps CSV

    Returns:
        DataFrame with columns: frame_index, timestamp_ms
    """
    df = pd.read_csv(csv_path)
    required_cols = {"frame_index", "timestamp_ms"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required_cols}")
    return df


def load_data_series(csv_path: Path) -> pd.DataFrame:
    """
    Load time-series data from CSV.

    CSV must contain 'timestamp_ms' column, other columns are flexible.

    Args:
        csv_path: Path to data series CSV

    Returns:
        DataFrame with timestamp_ms and data columns
    """
    df = pd.read_csv(csv_path)
    if "timestamp_ms" not in df.columns:
        raise ValueError("CSV must contain 'timestamp_ms' column")
    return df.sort_values("timestamp_ms")


def load_jsonl(jsonl_path: Path) -> List[dict]:
    """
    Load time-series data from JSONL file.

    JSONL (JSON Lines) format: one JSON object per line.
    Each object must contain 'timestamp_ms' field.

    Example JSONL:
        {"timestamp_ms": 0.0, "speed": 120.5, "gps": {"lat": 39.9, "lon": 116.4}}
        {"timestamp_ms": 50.0, "speed": 125.3, "gps": {"lat": 39.91, "lon": 116.41}}

    Args:
        jsonl_path: Path to JSONL file

    Returns:
        List of data dictionaries sorted by timestamp_ms

    Raises:
        ValueError: If any record is missing timestamp_ms
    """
    import json

    data = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}")

            if "timestamp_ms" not in record:
                raise ValueError(
                    f"Line {line_num} missing required field 'timestamp_ms'"
                )

            data.append(record)

    # Sort by timestamp
    data.sort(key=lambda x: x["timestamp_ms"])
    return data


def save_jsonl(data: List[dict], jsonl_path: Path) -> None:
    """
    Save data to JSONL file.

    Args:
        data: List of dictionaries to save
        jsonl_path: Output path for JSONL file
    """
    import json

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for record in data:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
