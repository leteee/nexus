"""
Type definitions for data replay system.

Defines data structures for frame timing, data points, and rendering protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Protocol

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
    data: dict[str, Any]  # Flexible data payload


@dataclass
class VideoMetadata:
    """Metadata about extracted video frames."""

    total_frames: int
    fps: float
    width: int
    height: int
    output_dir: Path


class DataRenderer(Protocol):
    """
    Abstract interface for rendering data onto video frames.

    Each data type (e.g., speed, GPS, sensor readings) should implement
    this protocol to define:
    1. How to match data points to frame timestamps
    2. How to visualize data on frames
    """

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[DataPoint]:
        """
        Find data points matching the given timestamp within tolerance.

        Args:
            timestamp_ms: Target timestamp in milliseconds
            tolerance_ms: Acceptable time difference

        Returns:
            List of matching data points
        """
        ...

    def render_on_frame(
        self,
        frame: np.ndarray,
        data: List[DataPoint],
    ) -> np.ndarray:
        """
        Draw data visualization on the frame.

        Args:
            frame: Video frame as numpy array (H, W, C)
            data: Matched data points to render

        Returns:
            Frame with data rendered
        """
        ...


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
