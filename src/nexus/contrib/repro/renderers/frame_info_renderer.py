"""
Frame info renderer for displaying frame metadata on video frames.

Renders frame index and timestamp information using the centralized draw_textbox utility.
"""

from __future__ import annotations

import logging
from typing import Optional, Any, Dict, List

import numpy as np

from ..types import DataRenderer
from ..common.time_utils import TimeProvider
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
        self.time = TimeProvider()

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
            
        timestamp_ms_raw = data.get("snapshot_time_ms")
        if timestamp_ms_raw is None:
            return frame
        timestamp_ms = float(timestamp_ms_raw)

        frame_idx = self.ctx.recall("current_frame_idx", default=0)
        self.logger.debug(f"Rendering frame info for frame {frame_idx}")

        lines: List[str] = []
        if self.format == "compact":
            datetime_str = self.time.format(timestamp_ms, fmt="time")
            lines.append(f"Frame: {frame_idx}  {datetime_str}")

        elif self.format == "datetime":
            datetime_str = self.time.format(timestamp_ms, fmt="datetime")
            lines.append(f"Frame: {frame_idx}  {datetime_str}")

        elif self.format == "detailed":
            datetime_str = self.time.format(timestamp_ms, fmt="iso")
            lines.extend(
                [
                    f"Frame: {frame_idx}",
                    f"TS: {timestamp_ms:.0f}ms",
                    f"Time: {datetime_str}",
                ]
            )
        else:
            self.logger.warning("Unknown format '%s', using 'datetime' as default", self.format)
            datetime_str = self.time.format(timestamp_ms, fmt="datetime")
            lines.append(f"Frame: {frame_idx}  {datetime_str}")

        # With the new API, drawing single or multi-line text is identical
        draw_textbox(frame, lines, self.textbox_config)

        return frame
