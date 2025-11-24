"""
Frame info renderer for displaying frame metadata on video frames.

Renders frame index and timestamp information in configurable position and format.
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from ..types import TextAlignment
from ..utils import resolve_position, timestamp_to_string


class FrameInfoRenderer:
    """
    Render frame information (frame index and timestamp) on video frames.
    """

    def __init__(
        self,
        ctx: Any,
        format: str = "datetime",
        style: dict | TextAlignment = None,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access.
            format: Display format - "compact", "datetime", or "detailed".
            style: Text styling and positioning configuration.
        """
        self.ctx = ctx
        self.format = format
        
        if style is None:
            self.style = TextAlignment()
        elif isinstance(style, dict):
            self.style = TextAlignment.model_validate(style)
        else:
            self.style = style

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Render frame info on frame.
        """
        frame_idx = self.ctx.recall("current_frame_idx", 0)
        self.ctx.logger.debug(f"Rendering frame info at frame {frame_idx}, timestamp {timestamp_ms}ms")

        # Format text based on selected format
        if self.format == "compact":
            text = f"Frame: {frame_idx}  TS: {timestamp_ms}ms"
            self._draw_text(frame, text)

        elif self.format == "datetime":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            text = f"Frame: {frame_idx}  TS: {timestamp_ms}ms  Time: {datetime_str}"
            self._draw_text(frame, text)

        elif self.format == "detailed":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines = [
                f"Frame: {frame_idx}",
                f"TS: {timestamp_ms}ms",
                f"Time: {datetime_str}",
            ]
            
            # For multiline, we resolve the position of the first line
            # and then draw subsequent lines below it.
            initial_pos = resolve_position(frame, lines[0], self.style.font_scale, self.style.thickness, self.style.position)
            
            line_height = int(30 * self.style.font_scale) # Approximate line height
            for i, line in enumerate(lines):
                # Use the resolved x of the first line and increment y for subsequent lines.
                pos = (initial_pos[0], initial_pos[1] + i * line_height)
                self._draw_single_line(frame, line, pos)

        else:
            self.ctx.logger.warning(f"Unknown format '{self.format}', using 'datetime' as default")
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            text = f"Frame: {frame_idx}  TS: {timestamp_ms}ms  Time: {datetime_str}"
            self._draw_text(frame, text)

        return frame

    def _draw_text(self, frame: np.ndarray, text: str) -> None:
        """Draws a single line of text using the resolved position."""
        pos = resolve_position(frame, text, self.style.font_scale, self.style.thickness, self.style.position)
        self._draw_single_line(frame, text, pos)

    def _draw_single_line(self, frame: np.ndarray, text: str, position: tuple[int, int]) -> None:
        """Draws text at a specific pixel coordinate."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        outline_color = (0, 0, 0)
        outline_thickness = self.style.thickness + 2

        cv2.putText(
            frame, text, position, font, self.style.font_scale,
            outline_color, outline_thickness, cv2.LINE_AA
        )
        cv2.putText(
            frame, text, position, font, self.style.font_scale,
            self.style.color, self.style.thickness, cv2.LINE_AA
        )