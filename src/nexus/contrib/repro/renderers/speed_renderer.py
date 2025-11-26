"""
Speed renderer for displaying vehicle speed on video frames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any, Dict, Union

import numpy as np

from .base import BaseDataRenderer
from ..utils_text import draw_textbox, TextboxConfig


class SpeedRenderer(BaseDataRenderer):
    """
    Renders vehicle speed on video frames.
    Styling and position are controlled by a TextboxConfig object.
    """

    def __init__(
        self,
        ctx: Any,
        data_path: Union[str, Path],
        tolerance_ms: float = 5000.0,
        time_offset_ms: int = 0,
        show_timestamp: bool = True,
        textbox_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            ctx: Context object.
            data_path: Path to speed JSONL file.
            tolerance_ms: Forward matching tolerance.
            time_offset_ms: Time offset for data timestamp bias.
            show_timestamp: Whether to show data and adjusted timestamps.
            textbox_config: Dictionary defining the text's appearance and position.
        """
        super().__init__(
            ctx=ctx,
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="forward",
            time_offset_ms=time_offset_ms,
        )

        self.show_timestamp = show_timestamp
        self.textbox_config = TextboxConfig.from_dict(textbox_config)

    def render(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
        """
        Renders speed on the frame.
        """
        matched = self.match_data(timestamp_ms)

        lines = []
        if not matched or "speed" not in matched[0]:
            lines.append("Speed: N/A")
        else:
            speed_value = matched[0]['speed']
            lines.append(f"Speed: {speed_value:.1f} km/h")

            if self.show_timestamp:
                data_timestamp = matched[0].get('timestamp_ms', 'N/A')
                adjusted_timestamp = timestamp_ms - self.time_offset_ms
                lines.append(f"[Data: {int(data_timestamp)}ms | Adj: {adjusted_timestamp}ms]")

        if lines:
            draw_textbox(frame, lines, self.textbox_config)

        return frame