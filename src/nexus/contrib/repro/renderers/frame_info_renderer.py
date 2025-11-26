"""
Frame info renderer for displaying frame metadata on video frames.

Renders frame index and timestamp information using the centralized draw_textbox utility.
"""

from __future__ import annotations

from typing import Optional, Any, Dict, List

import numpy as np

from ..utils import timestamp_to_string
from ..utils_text import draw_textbox, TextboxConfig


class FrameInfoRenderer:
    """
    Renders frame information (frame index and timestamp) on video frames.
    Styling and position are controlled by a TextboxConfig object.
    """

    def __init__(
        self,
        ctx: Any,
        format: str = "datetime",
        textbox_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            ctx: Context object providing logger and shared state.
            format: Display format - "compact", "datetime", or "detailed".
            textbox_config: A dictionary defining the text's appearance and position,
                            matching the structure of TextboxConfig.
        """
        self.ctx = ctx
        self.format = format
        self.textbox_config = TextboxConfig.from_dict(textbox_config)

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Renders frame info on the given frame.

        Args:
            frame: Video frame (H, W, C) in BGR format.
            timestamp_ms: Frame timestamp in milliseconds.

        Returns:
            The frame with the information rendered on it.
        """
        frame_idx = self.ctx.recall("current_frame_idx", default=0)
        self.ctx.logger.debug(f"Rendering frame info for frame {frame_idx}")

        lines: List[str] = []
        if self.format == "compact":
            lines.append(f"Frame: {frame_idx}  TS: {timestamp_ms}ms")

        elif self.format == "datetime":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines.append(f"Frame: {frame_idx}  TS: {timestamp_ms}ms  Time: {datetime_str}")

        elif self.format == "detailed":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines.extend([
                f"Frame: {frame_idx}",
                f"TS: {timestamp_ms}ms",
                f"Time: {datetime_str}",
            ])
        else:
            # Default to 'datetime' format if an unknown format is provided
            self.ctx.logger.warning(f"Unknown format '{self.format}', using 'datetime' as default")
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines.append(f"Frame: {frame_idx}  TS: {timestamp_ms}ms  Time: {datetime_str}")

        # With the new API, drawing single or multi-line text is identical
        draw_textbox(frame, lines, self.textbox_config)

        return frame