"""Vehicle speed renderer."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import Field, field_validator

from ..models import ReproModel
from ..text import TextboxStyle, draw_textbox
from .base import RenderContext, Renderer, register_renderer


class SpeedConfig(ReproModel):
    """Configuration for :class:`SpeedRenderer`."""

    sensor: str = Field(default="speed", description="Role name in RendererSpec.sensors.")
    show_timestamp: bool = True
    style: TextboxStyle = Field(default_factory=TextboxStyle)

    @field_validator("style", mode="before")
    @classmethod
    def _coerce_style(cls, value: Any) -> Any:
        return TextboxStyle.from_mapping(value)


@register_renderer("speed")
class SpeedRenderer(Renderer[SpeedConfig]):
    """Draw vehicle speed and optional timestamp traceability."""

    Config = SpeedConfig

    def render(self, frame: np.ndarray, context: RenderContext) -> np.ndarray:
        match = context.sensors.get(self.config.sensor)
        lines: list[str] = []
        if match is None or "speed" not in match.data:
            lines.append("Speed: N/A")
        else:
            speed = float(match.data["speed"])
            lines.append(f"Speed: {speed:.1f} km/h")
            if self.config.show_timestamp:
                lines.append(
                    f"[Data: {match.world_timestamp_ms:.0f} | Snap: {match.snapshot_ms:.0f}]"
                )
        draw_textbox(frame, lines, self.config.style)
        return frame
