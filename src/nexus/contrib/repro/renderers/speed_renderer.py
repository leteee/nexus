"""
Speed renderer for displaying vehicle speed on video frames.

Renders speed data in top-left corner with configurable position and styling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

import cv2
import numpy as np

from .base import BaseDataRenderer


class SpeedRenderer(BaseDataRenderer):
    """
    Render vehicle speed on video frames.

    Features:
    - Displays speed in km/h (or N/A if no data)
    - Configurable position and styling
    - Forward matching (speed "holds" until next update)
    - Background panel for readability

    Data format (JSONL):
        {"timestamp_ms": 1759284000000.0, "speed": 120.5}
        {"timestamp_ms": 1759284005000.0, "speed": 125.3}

    Example:
        >>> renderer = SpeedRenderer(
        ...     data_path="input/speed.jsonl",
        ...     position=(30, 60),
        ...     tolerance_ms=5000.0,  # Hold speed for up to 5s
        ... )
        >>> frame = cv2.imread("frame_0000.png")
        >>> frame = renderer.render(frame, timestamp_ms=1759284000000.0)
    """

    def __init__(
        self,
        data_path: Union[Path, str],
        position: Tuple[int, int] = (30, 60),
        tolerance_ms: float = 5000.0,
        time_offset_ms: int = 0,
        font_scale: float = 1.2,
        color: Tuple[int, int, int] = (0, 255, 0),  # BGR: Green
        thickness: int = 3,
    ):
        """
        Args:
            data_path: Path to speed JSONL file
            position: (x, y) position for text (top-left anchor)
            tolerance_ms: Forward matching tolerance (default 5000ms)
            time_offset_ms: Time offset to apply to data timestamps (int, default 0ms)
            font_scale: Font size multiplier
            color: Text color in BGR format
            thickness: Text thickness
        """
        # Use forward matching for speed (holds value)
        super().__init__(
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="forward",
            time_offset_ms=time_offset_ms,
        )

        self.position = position
        self.font_scale = font_scale
        self.color = color
        self.thickness = thickness

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Render speed on frame.

        Args:
            frame: Video frame (H, W, C) in BGR format
            timestamp_ms: Frame timestamp in milliseconds

        Returns:
            Frame with speed rendered
        """
        # Match speed data
        matched = self.match_data(timestamp_ms)

        # Prepare text
        if not matched or "speed" not in matched[0]:
            speed_str = "N/A"
        else:
            speed_str = f"{matched[0]['speed']:.1f} km/h"

        text = f"Speed: {speed_str}"

        # Draw with background
        x, y = self.position
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Get text size
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, self.font_scale, self.thickness
        )

        # Draw background rectangle
        padding = 10
        cv2.rectangle(
            frame,
            (x - padding, y - text_h - padding),
            (x + text_w + padding, y + baseline + padding),
            (0, 0, 0),  # Black background
            -1,
        )

        # Draw text
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            self.font_scale,
            self.color,
            self.thickness,
            cv2.LINE_AA,
        )

        return frame
