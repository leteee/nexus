"""
Speed renderer for displaying vehicle speed on video frames.

Renders speed data in top-left corner with configurable position and styling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union, Optional, Any

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
    - Text with outline for readability (no background panel)

    Data format (JSONL):
        {"timestamp_ms": 1759284000000.0, "speed": 120.5}
        {"timestamp_ms": 1759284005000.0, "speed": 125.3}

    Example:
        >>> renderer = SpeedRenderer(
        ...     ctx=ctx,  # Pass PluginContext
        ...     data_path="input/speed.jsonl",
        ...     position=(30, 60),
        ...     tolerance_ms=5000.0,  # Hold speed for up to 5s
        ... )
        >>> frame = cv2.imread("frame_0000.png")
        >>> frame = renderer.render(frame, timestamp_ms=1759284000000.0)
    """

    def __init__(
        self,
        ctx: Any,
        data_path: Union[Path, str],
        position: Tuple[int, int] = (30, 60),
        tolerance_ms: float = 5000.0,
        time_offset_ms: int = 0,
        font_scale: float = 1.2,
        color: Tuple[int, int, int] = (0, 255, 0),  # BGR: Green
        thickness: int = 3,
        show_timestamp: bool = True,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access
            data_path: Path to speed JSONL file
            position: (x, y) position for text (top-left anchor)
            tolerance_ms: Forward matching tolerance (default 5000ms)
            time_offset_ms: Time offset to correct data timestamp bias (int, default 0ms)
            font_scale: Font size multiplier
            color: Text color in BGR format
            thickness: Text thickness
            show_timestamp: Whether to show data and adjusted timestamps (default True)
        """
        # Use forward matching for speed (holds value)
        super().__init__(
            ctx=ctx,
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="forward",
            time_offset_ms=time_offset_ms,
        )

        self.position = position
        self.font_scale = font_scale
        self.color = color
        self.thickness = thickness
        self.show_timestamp = show_timestamp

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Render speed on frame.

        Args:
            frame: Video frame (H, W, C) in BGR format
            timestamp_ms: Frame timestamp in milliseconds

        Returns:
            Frame with speed rendered
        """
        # Log rendering start
        self.ctx.logger.debug(f"Rendering speed at timestamp {timestamp_ms}ms")

        # Match speed data
        matched = self.match_data(timestamp_ms)

        # Prepare text
        if not matched or "speed" not in matched[0]:
            speed_str = "N/A"
            data_ts_str = ""
            self.ctx.logger.debug(f"No speed data found for timestamp {timestamp_ms}ms")
        else:
            speed_value = matched[0]['speed']
            data_timestamp = matched[0].get('timestamp_ms', 'N/A')
            speed_str = f"{speed_value:.1f} km/h"

            # Show timestamps if enabled
            if self.show_timestamp:
                adjusted_timestamp = timestamp_ms - self.time_offset_ms
                data_ts_str = f"  [Data: {data_timestamp}ms | Adj: {adjusted_timestamp}ms]"
            else:
                data_ts_str = ""

            self.ctx.logger.debug(f"Matched speed data: {speed_value:.1f} km/h at {data_timestamp}ms")

        text = f"Speed: {speed_str}{data_ts_str}"

        # Draw text with outline (no background panel)
        x, y = self.position
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Draw text outline (black) for better visibility
        outline_color = (0, 0, 0)
        outline_thickness = self.thickness + 2

        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            self.font_scale,
            outline_color,
            outline_thickness,
            cv2.LINE_AA,
        )

        # Draw main text
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
