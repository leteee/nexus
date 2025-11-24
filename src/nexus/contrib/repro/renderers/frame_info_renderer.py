"""
Frame info renderer for displaying frame metadata on video frames.

Renders frame index and timestamp information in configurable position and format.
"""

from __future__ import annotations

from typing import Tuple, Optional, Any

import cv2
import numpy as np

from ..utils import timestamp_to_string


class FrameInfoRenderer:
    """
    Render frame information (frame index and timestamp) on video frames.

    Features:
    - Displays frame ID and timestamp
    - Configurable position and styling
    - Multiple format options (compact, datetime, detailed)
    - Text with outline for readability (no background panel)

    Example:
        >>> renderer = FrameInfoRenderer(
        ...     ctx=ctx,  # Pass PluginContext
        ...     position=[10, 30],
        ...     format="datetime",
        ...     font_scale=0.6,
        ...     color=[0, 255, 255],  # Yellow
        ... )
        >>> frame = cv2.imread("frame_0000.png")
        >>> frame = renderer.render(frame, timestamp_ms=1759284000000)
    """

    def __init__(
        self,
        ctx: Any,
        position: Tuple[int, int] = (10, 30),
        format: str = "datetime",
        font_scale: float = 0.6,
        color: Tuple[int, int, int] = (0, 255, 255),  # Yellow
        thickness: int = 1,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access
            position: (x, y) position for text (top-left anchor)
            format: Display format - "compact", "datetime", or "detailed"
                - compact: "Frame: 123  TS: 1759284000000ms"
                - datetime: "Frame: 123  TS: 1759284000000ms  Time: 2025-10-27 08:30:10"
                - detailed: Multi-line with date and time
            font_scale: Font size multiplier
            color: Text color in BGR format
            thickness: Text thickness
        """
        self.ctx = ctx
        self.position = position
        self.format = format
        self.font_scale = font_scale
        self.color = color
        self.thickness = thickness

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Render frame info on frame.

        Args:
            frame: Video frame (H, W, C) in BGR format
            timestamp_ms: Frame timestamp in milliseconds

        Returns:
            Frame with frame info rendered

        Note:
            frame_idx is retrieved from ctx.recall("current_frame_idx")
        """
        # Get frame_idx from context (set by render_all_frames in video.py)
        frame_idx = self.ctx.recall("current_frame_idx")
        if frame_idx is None:
            self.ctx.logger.warning("frame_idx not found in context, using 0")
            frame_idx = 0

        # Log rendering start
        self.ctx.logger.debug(f"Rendering frame info at frame {frame_idx}, timestamp {timestamp_ms}ms")

        # Format text based on selected format
        if self.format == "compact":
            text = f"Frame: {frame_idx}  TS: {timestamp_ms}ms"
            self._draw_text(frame, text, self.position)

        elif self.format == "datetime":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            text = f"Frame: {frame_idx}  TS: {timestamp_ms}ms  Time: {datetime_str}"
            self._draw_text(frame, text, self.position)

        elif self.format == "detailed":
            # Multi-line format
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines = [
                f"Frame: {frame_idx}",
                f"TS: {timestamp_ms}ms",
                f"Time: {datetime_str}",
            ]
            x, y = self.position
            line_height = int(25 * self.font_scale)
            for i, line in enumerate(lines):
                self._draw_text(frame, line, (x, y + i * line_height))

        else:
            self.ctx.logger.warning(f"Unknown format '{self.format}', using 'datetime' as default")
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            text = f"Frame: {frame_idx}  TS: {timestamp_ms}ms  Time: {datetime_str}"
            self._draw_text(frame, text, self.position)

        return frame

    def _draw_text(self, frame: np.ndarray, text: str, position: Tuple[int, int]) -> None:
        """
        Draw text with outline for better visibility.

        Args:
            frame: Video frame to draw on
            text: Text to draw
            position: (x, y) position
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        outline_color = (0, 0, 0)  # Black outline
        outline_thickness = self.thickness + 2

        # Draw text outline
        cv2.putText(
            frame,
            text,
            position,
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
            position,
            font,
            self.font_scale,
            self.color,
            self.thickness,
            cv2.LINE_AA,
        )
