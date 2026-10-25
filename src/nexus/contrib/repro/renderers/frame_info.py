"""Frame index and timestamp renderer."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import Field, field_validator

from ..models import ReproModel
from ..text import TextboxStyle, draw_textbox
from ..time import TimeProvider
from .base import RenderContext, Renderer, register_renderer


class FrameInfoConfig(ReproModel):
    """Configuration for :class:`FrameInfoRenderer`."""

    format: Literal["compact", "datetime", "detailed"] = "datetime"
    style: TextboxStyle = Field(default_factory=TextboxStyle)

    @field_validator("style", mode="before")
    @classmethod
    def _coerce_style(cls, value: Any) -> Any:
        return TextboxStyle.from_mapping(value)


@register_renderer("frame_info")
class FrameInfoRenderer(Renderer[FrameInfoConfig]):
    """Draw the frame index and its formatted timestamp."""

    Config = FrameInfoConfig

    def __init__(self, config: FrameInfoConfig) -> None:
        super().__init__(config)
        self.time = TimeProvider()

    def render(self, frame: np.ndarray, context: RenderContext) -> np.ndarray:
        timestamp_ms = context.timestamp_ms
        if self.config.format == "compact":
            datetime_str = self.time.format(timestamp_ms, fmt="time")
            lines = [f"Frame: {context.frame_index}  {datetime_str}"]
        elif self.config.format == "detailed":
            datetime_str = self.time.format(timestamp_ms, fmt="iso")
            lines = [
                f"Frame: {context.frame_index}",
                f"TS: {timestamp_ms:.0f}ms",
                f"Time: {datetime_str}",
            ]
        else:
            datetime_str = self.time.format(timestamp_ms, fmt="datetime")
            lines = [f"Frame: {context.frame_index}  {datetime_str}"]
        draw_textbox(frame, lines, self.config.style)
        return frame
