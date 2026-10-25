"""ADB target box renderer."""

from __future__ import annotations

from typing import Any, Literal

import cv2
import numpy as np
from pydantic import Field, field_validator

from ..camera import CameraModel
from ..models import ReproModel
from ..text import TextboxStyle, draw_textbox
from .base import RenderContext, Renderer, register_renderer


class TargetConfig(ReproModel):
    """Configuration for :class:`TargetRenderer`."""

    sensor: str = Field(default="targets", description="Role name in RendererSpec.sensors.")
    camera: str = Field(default="auto", description="Camera calibration path or 'auto'.")
    display: Literal["distance", "angle"] = "distance"
    box_color: tuple[int, int, int] | None = None
    box_thickness: int | None = Field(default=None, ge=1)
    show_box_label: bool = True
    show_timestamp: bool = True
    style: TextboxStyle = Field(default_factory=TextboxStyle)

    @field_validator("style", mode="before")
    @classmethod
    def _coerce_style(cls, value: Any) -> Any:
        return TextboxStyle.from_mapping(value)


@register_renderer("target")
class TargetRenderer(Renderer[TargetConfig]):
    """Project ADB target angles to image boxes and draw an info panel."""

    Config = TargetConfig

    def __init__(self, config: TargetConfig) -> None:
        super().__init__(config)
        self.camera = CameraModel.load(config.camera)
        self.box_color = config.box_color or config.style.text_color
        self.box_thickness = config.box_thickness or config.style.font.thickness

    def _draw_box(self, frame: np.ndarray, projected: Any) -> tuple[tuple[int, int], tuple[int, int]]:
        x_coords = [point[0] for point in projected.corners]
        y_coords = [point[1] for point in projected.corners]
        top_left = (min(x_coords), min(y_coords))
        bottom_right = (max(x_coords), max(y_coords))
        cv2.rectangle(frame, top_left, bottom_right, self.box_color, self.box_thickness)
        if self.config.show_box_label:
            label = f"ID:{projected.target.get('id', 'N/A')}"
            label_position = (top_left[0], max(top_left[1] - 10, 15))
            cv2.putText(
                frame,
                label,
                label_position,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                label,
                label_position,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                self.box_color,
                1,
                cv2.LINE_AA,
            )
        return top_left, bottom_right

    def render(self, frame: np.ndarray, context: RenderContext) -> np.ndarray:
        height, width = frame.shape[:2]
        self.camera.validate_frame_size(width, height)
        match = context.sensors.get(self.config.sensor)
        if match is None:
            return frame
        targets = match.data.get("targets") or []
        if not targets:
            return frame

        rendered: list[tuple[dict[str, Any], Any]] = []
        for target in targets:
            projected = self.camera.project_target_box(target)
            if projected is None:
                continue
            self._draw_box(frame, projected)
            rendered.append((target, projected))

        if not rendered:
            return frame

        lines = [f"Targets: {len(rendered)}"]
        for target, projected in rendered:
            if self.config.display == "angle":
                bounds = (
                    f"AL:{float(target['angle_left']):.1f}deg "
                    f"AR:{float(target['angle_right']):.1f}deg "
                    f"AT:{float(target['angle_top']):.1f}deg "
                    f"AB:{float(target['angle_bottom']):.1f}deg"
                )
            else:
                ads = projected.ads_bounds
                bounds = (
                    f"XL:{ads['x_left']:.1f} XR:{ads['x_right']:.1f} "
                    f"YT:{ads['y_top']:.1f} YB:{ads['y_bottom']:.1f}"
                )
            lines.append(
                f"  ID:{target.get('id', 'N/A')} {target.get('type', 'N/A')} "
                f"D:{float(target['distance_m']):.1f}m {bounds}"
            )
        if self.config.show_timestamp:
            lines.append(
                f"[Data: {match.world_timestamp_ms:.0f}ms | Snap: {match.snapshot_ms:.0f}ms]"
            )
        draw_textbox(frame, lines, self.config.style)
        return frame
