"""
Speed renderer for displaying vehicle speed on video frames.

Renders speed data in top-left corner with configurable position and styling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import cv2
import numpy as np

from ..types import TextAlignment
from ..utils import resolve_position
from .base import BaseDataRenderer


class SpeedRenderer(BaseDataRenderer):
    """
    Render vehicle speed on video frames.
    """

    def __init__(
        self,
        ctx: Any,
        data_path: Union[Path, str],
        tolerance_ms: float = 5000.0,
        time_offset_ms: int = 0,
        show_timestamp: bool = True,
        style: dict | TextAlignment = None,
    ):
        """
        Args:
            ctx: Context object providing logger, path resolution, shared state access
            data_path: Path to speed JSONL file
            tolerance_ms: Forward matching tolerance (default 5000ms)
            time_offset_ms: Time offset to correct data timestamp bias (int, default 0ms)
            show_timestamp: Whether to show data and adjusted timestamps (default True)
            style: Text styling and positioning configuration.
        """
        super().__init__(
            ctx=ctx,
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="forward",
            time_offset_ms=time_offset_ms,
        )

        if style is None:
            # Maintain original defaults if no style is provided
            self.style = TextAlignment(font_scale=1.2, color=(0, 255, 0), thickness=3, position=(30, 60))
        elif isinstance(style, dict):
            self.style = TextAlignment.model_validate(style)
        else:
            self.style = style

        self.show_timestamp = show_timestamp

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Render speed on frame.
        """
        self.ctx.logger.debug(f"Rendering speed at timestamp {timestamp_ms}ms")

        matched = self.match_data(timestamp_ms)

        if not matched or "speed" not in matched[0]:
            speed_str = "N/A"
            data_ts_str = ""
            self.ctx.logger.debug(f"No speed data found for timestamp {timestamp_ms}ms")
        else:
            speed_value = matched[0]['speed']
            data_timestamp = matched[0].get('timestamp_ms', 'N/A')
            speed_str = f"{speed_value:.1f} km/h"

            if self.show_timestamp:
                adjusted_timestamp = timestamp_ms - self.time_offset_ms
                data_ts_str = f"  [Data: {data_timestamp}ms | Adj: {adjusted_timestamp}ms]"
            else:
                data_ts_str = ""
            self.ctx.logger.debug(f"Matched speed data: {speed_value:.1f} km/h at {data_timestamp}ms")

        text = f"Speed: {speed_str}{data_ts_str}"
        
        position = resolve_position(frame, text, self.style.font_scale, self.style.thickness, self.style.position)

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

        return frame