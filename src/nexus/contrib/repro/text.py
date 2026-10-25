"""Typed text-box styling and drawing."""

from __future__ import annotations

import ast
from typing import Any, Literal

import cv2
import numpy as np
from pydantic import Field, field_validator

from .models import ReproModel

AnchorPoint = Literal[
    "top_left",
    "top_center",
    "top_right",
    "center_left",
    "center",
    "center_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
]


class FontStyle(ReproModel):
    """Font properties for a text box."""

    face: int = Field(default=cv2.FONT_HERSHEY_SIMPLEX, description="OpenCV font face.")
    scale: float = Field(default=0.8, gt=0)
    thickness: int = Field(default=1, ge=1)
    line_spacing: float = Field(default=1.5, gt=0)


class PanelStyle(ReproModel):
    """Optional background panel behind a text box."""

    enabled: bool = False
    padding: int = Field(default=10, ge=0)
    bg_color: tuple[int, int, int] = (40, 40, 40)
    bg_alpha: float = Field(default=0.7, ge=0.0, le=1.0)
    border_color: tuple[int, int, int] | None = (100, 100, 100)
    border_thickness: int = Field(default=1, ge=0)


class PositionStyle(ReproModel):
    """Anchor point and coordinates for a text box."""

    x: int | str = 10
    y: int | str = 10
    anchor: AnchorPoint = "top_left"


class TextboxStyle(ReproModel):
    """Complete text box style."""

    position: PositionStyle = Field(default_factory=PositionStyle)
    font: FontStyle = Field(default_factory=FontStyle)
    panel: PanelStyle = Field(default_factory=PanelStyle)
    text_color: tuple[int, int, int] = (255, 255, 255)
    outline_color: tuple[int, int, int] | None = None
    outline_thickness: int = Field(default=3, ge=0)

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | TextboxStyle | None) -> TextboxStyle:
        if isinstance(data, cls):
            return data
        return cls.model_validate(data or {})

    @field_validator("position", "font", "panel", mode="before")
    @classmethod
    def _coerce_nested(cls, value: Any) -> Any:
        return value or {}


def _evaluate_coord(expr: int | str, frame_width: int, frame_height: int) -> int:
    """Evaluate a coordinate such as ``width - 10`` without using eval()."""

    if isinstance(expr, int):
        return expr
    if not isinstance(expr, str):
        raise ValueError(f"coordinate must be an int or string, got {type(expr).__name__}")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid coordinate expression: {expr!r}") from exc

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id == "width":
                return float(frame_width)
            if node.id == "height":
                return float(frame_height)
            raise ValueError(f"unknown name {node.id!r} in coordinate expression")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)):
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            return left % right
        raise ValueError(f"unsupported coordinate expression: {expr!r}")

    try:
        return int(evaluate(tree))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"invalid coordinate expression {expr!r}: {exc}") from exc


def _calculate_text_dimensions(lines: list[str], font: FontStyle) -> tuple[int, int, int]:
    if not lines:
        return 0, 0, 0
    (_, sample_height), baseline = cv2.getTextSize("Tg", font.face, font.scale, font.thickness)
    single_line_height = int(sample_height * font.line_spacing + baseline)
    total_height = single_line_height * len(lines)
    max_width = 0
    for line in lines:
        (line_width, _), _ = cv2.getTextSize(line, font.face, font.scale, font.thickness)
        max_width = max(max_width, line_width)
    return max_width, total_height, single_line_height


def _calculate_box_top_left(
    target_x: int,
    target_y: int,
    anchor: AnchorPoint,
    box_width: int,
    box_height: int,
) -> tuple[int, int]:
    if "left" in anchor:
        pass
    elif "right" in anchor:
        target_x -= box_width
    else:
        target_x -= box_width // 2

    if "top" in anchor:
        pass
    elif "bottom" in anchor:
        target_y -= box_height
    else:
        target_y -= box_height // 2

    return target_x, target_y


def draw_textbox(frame: np.ndarray, lines: list[str], style: TextboxStyle) -> None:
    """Draw a multiline text box on a BGR frame in place."""

    if not lines or not lines[0]:
        return

    frame_height, frame_width, _ = frame.shape
    text_width, text_height, line_height = _calculate_text_dimensions(lines, style.font)

    container_width, container_height = text_width, text_height
    if style.panel.enabled:
        container_width += style.panel.padding * 2
        container_height += style.panel.padding * 2

    target_x = _evaluate_coord(style.position.x, frame_width, frame_height)
    target_y = _evaluate_coord(style.position.y, frame_width, frame_height)
    top_left_x, top_left_y = _calculate_box_top_left(
        target_x,
        target_y,
        style.position.anchor,
        container_width,
        container_height,
    )

    if style.panel.enabled:
        bottom_right_x = top_left_x + container_width
        bottom_right_y = top_left_y + container_height
        if style.panel.bg_color and style.panel.bg_alpha > 0:
            overlay = frame.copy()
            cv2.rectangle(
                overlay,
                (top_left_x, top_left_y),
                (bottom_right_x, bottom_right_y),
                style.panel.bg_color,
                -1,
            )
            cv2.addWeighted(
                overlay,
                style.panel.bg_alpha,
                frame,
                1 - style.panel.bg_alpha,
                0,
                frame,
            )
        if style.panel.border_color and style.panel.border_thickness > 0:
            cv2.rectangle(
                frame,
                (top_left_x, top_left_y),
                (bottom_right_x, bottom_right_y),
                style.panel.border_color,
                style.panel.border_thickness,
            )

    text_start_x = top_left_x + style.panel.padding if style.panel.enabled else top_left_x
    text_start_y = top_left_y + style.panel.padding if style.panel.enabled else top_left_y

    for index, line in enumerate(lines):
        (_, line_height_px), baseline = cv2.getTextSize(
            line, style.font.face, style.font.scale, style.font.thickness
        )
        baseline_y = text_start_y + (index * line_height) + line_height_px
        if style.outline_color and style.outline_thickness > 0:
            cv2.putText(
                frame,
                line,
                (text_start_x, baseline_y),
                style.font.face,
                style.font.scale,
                style.outline_color,
                style.outline_thickness,
                cv2.LINE_AA,
            )
        cv2.putText(
            frame,
            line,
            (text_start_x, baseline_y),
            style.font.face,
            style.font.scale,
            style.text_color,
            style.font.thickness,
            cv2.LINE_AA,
        )
