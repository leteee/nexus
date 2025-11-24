"""
Type definitions for data replay system.

Defines data structures for frame timing, data points, and rendering protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Literal, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field


@dataclass
class VideoMetadata:
    """Metadata about extracted video frames."""

    total_frames: int
    fps: float
    width: int
    height: int
    output_path: Path


class Position(BaseModel):
    """
    Defines a position in 2D space with an anchor and relative/absolute coordinates.
    """
    anchor: Literal[
        "top_left", "top_center", "top_right",
        "center_left", "center", "center_right",
        "bottom_left", "bottom_center", "bottom_right"
    ] = Field(default="top_left", description="Anchor point on the object being placed.")
    coords: Tuple[float, float] = Field(..., description="[x, y] coordinates for the anchor in the frame.")
    is_relative: bool = Field(
        default=False,
        description="If true, coordinates are relative to frame dimensions (0.0-1.0). If false, they are absolute pixels."
    )


class TextAlignment(BaseModel):
    """
    Defines text styling and positioning.
    """
    position: Union[Position, Tuple[float, float]] = Field(
        default=(10, 30),
        description="Position of the text. Can be a simple [x, y] tuple (top-left anchor) or a detailed Position object."
    )
    color: Tuple[int, int, int] = Field(
        default=(0, 255, 255),
        description="Text color in BGR format (e.g., (0, 255, 255) for yellow)."
    )
    font_scale: float = Field(default=0.6, description="Font size multiplier.")
    thickness: int = Field(default=1, description="Text line thickness.")


class DataRenderer(ABC):
    """
    Abstract base class for rendering time-series data onto video frames.

    Subclasses define their own __init__ with required data sources,
    then implement the three core methods:
        1. load_data() - How to load data from file (JSONL/CSV/etc)
        2. match_data() - How to find data matching a timestamp
        3. render() - How to draw data on frame

    Example:
        >>> class SpeedRenderer(DataRenderer):
        ...     def __init__(self, data_path):
        ...         from nexus.contrib.repro.io import load_jsonl
        ...         self.data = load_jsonl(data_path)
        ...
        ...     def load_data(self, data_path):
        ...         pass  # Already loaded in __init__
        ...
        ...     def match_data(self, timestamp_ms, tolerance_ms=50.0):
        ...         # Find nearest data point
        ...         ...
        ...
        ...     def render(self, frame, data):
        ...         # Draw speed on frame
        ...         cv2.putText(frame, f"Speed: {data['speed']}", ...)
        ...         return frame
    """

    @abstractmethod
    def load_data(self, data_path: Path) -> None:
        """
        Load time-series data from file.

        Note: This method may not be called if data is loaded in __init__.
        Kept for interface compatibility.

        Args:
            data_path: Path to data file
        """
        raise NotImplementedError

    @abstractmethod
    def match_data(
        self,
        timestamp_ms: int,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """
        Find data points matching the given timestamp.

        Args:
            timestamp_ms: Target timestamp in milliseconds (int)
            tolerance_ms: Maximum acceptable time difference (ms)

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
        timestamp_ms: int,
    ) -> np.ndarray:
        """
        Render data visualization onto frame.

        This method internally calls match_data() with the timestamp,
        then renders the matched data. Context is accessible via self.ctx.

        Args:
            frame: Video frame as numpy array (H, W, C) in BGR format
            timestamp_ms: Frame timestamp in milliseconds (int)

        Returns:
            Frame with data rendered (modified in-place or copied)

        Example:
            >>> def render(self, frame, timestamp_ms):
            ...     # Match data for this timestamp
            ...     matched = self.match_data(timestamp_ms)
            ...     if not matched:
            ...         return frame
            ...     # Use context for logging
            ...     self.ctx.logger.debug(f"Rendering data at {timestamp_ms}ms")
            ...     # Render the data
            ...     speed = matched[0].get('speed', 0)
            ...     cv2.putText(frame, f"Speed: {speed:.1f}", (20, 50), ...)
            ...     return frame
        """
        raise NotImplementedError