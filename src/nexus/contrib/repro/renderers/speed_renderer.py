"""
Speed renderer for displaying vehicle speed on video frames.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Any, Dict, Union

import numpy as np

from ..types import DataRenderer
from ..common.utils_text import draw_textbox, TextboxConfig


class SpeedRenderer(DataRenderer):
    """
    Renders vehicle speed on video frames.
    Styling and position are controlled by a TextboxConfig object.
    This renderer expects to be "pushed" data from a SensorDataManager.
    """

    def __init__(
        self,
        ctx: Any,
        show_timestamp: bool = True,
        textbox_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """
        Args:
            ctx: Context object.
            show_timestamp: Whether to show snapshot and aligned timestamps.
            textbox_config: Dictionary defining the text's appearance and position.
            **kwargs: Catches unused arguments from old configs.
        """
        self.ctx = ctx
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        self.show_timestamp = show_timestamp
        self.textbox_config = TextboxConfig.from_dict(textbox_config)

    def render(self, frame: np.ndarray, data: Optional[Dict[str, Any]]) -> np.ndarray:
        """
        Renders speed on the frame from the provided data dictionary.
        """
        lines = []
        if not data or "speed" not in data:
            lines.append("Speed: N/A")
        else:
            speed_value = data['speed']
            lines.append(f"Speed: {speed_value:.1f} km/h")

            if self.show_timestamp:
                data_ts = float(data.get('timestamp_ms', 0.0))
                snapshot_ts = float(data.get('snapshot_time_ms', 0.0))
                lines.append(f"[Data: {data_ts:.0f} | Snap: {snapshot_ts:.0f}]")

        if lines:
            draw_textbox(frame, lines, self.textbox_config)

        return frame