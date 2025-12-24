"""
Frame info renderer for displaying frame metadata on video frames.

Renders frame index and timestamp information using the centralized draw_textbox utility.
"""

from __future__ import annotations

import logging
from typing import Optional, Any, Dict, List

import numpy as np

from ..types import DataRenderer
from ..common.time_utils import timestamp_to_string
from ..common.text_renderer import draw_textbox, TextboxConfig


class FrameInfoRenderer(DataRenderer):
    """
    Renders frame information (frame index and timestamp) on video frames.
    Styling and position are controlled by a TextboxConfig object.
    It does not use sensor data, but relies on the `snapshot_time_ms` passed
    in its data dictionary.
    """

    def __init__(
        self,
        ctx: Any,
        format: str = "datetime",
        textbox_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """
        Args:
            ctx: Context object providing shared state.
            format: Display format - "compact", "datetime", or "detailed".
            textbox_config: A dictionary defining the text's appearance and position.
            **kwargs: Catches unused arguments from old configs.
        """
        self.ctx = ctx
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        self.format = format
        self.textbox_config = TextboxConfig.from_dict(textbox_config)

    def render(self, frame: np.ndarray, data: Optional[Dict[str, Any]]) -> np.ndarray:
        """
        Renders frame info on the given frame.

        Args:
            frame: Video frame (H, W, C) in BGR format.
            data: A dictionary containing `snapshot_time_ms`. Other keys are ignored.

        Returns:
            The frame with the information rendered on it.
        """
        if not data:
            return frame
            
        timestamp_ms = float(data.get('snapshot_time_ms', 0.0))
        if timestamp_ms == 0.0:
            return frame

        frame_idx = self.ctx.recall("current_frame_idx", default=0)
        self.logger.debug(f"Rendering frame info for frame {frame_idx}")

        lines: List[str] = []
        if self.format == "compact":
            lines.append(f"Frame: {frame_idx}  TS: {timestamp_ms:.0f}ms")

        elif self.format == "datetime":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines.append(f"Frame: {frame_idx}  TS: {timestamp_ms:.0f}ms  Time: {datetime_str}")

        elif self.format == "detailed":
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines.extend([
                f"Frame: {frame_idx}",
                f"TS: {timestamp_ms:.0f}ms",
                f"Time: {datetime_str}",
            ])
        else:
            # Default to 'datetime' format if an unknown format is provided
            self.logger.warning(f"Unknown format '{self.format}', using 'datetime' as default")
            datetime_str = timestamp_to_string(timestamp_ms, fmt="datetime")
            lines.append(f"Frame: {frame_idx}  TS: {timestamp_ms:.0f}ms  Time: {datetime_str}")

        # With the new API, drawing single or multi-line text is identical
        draw_textbox(frame, lines, self.textbox_config)

        return frame