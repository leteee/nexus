"""
Rendering utilities and base implementations for data visualization on frames.

Provides abstract interface and common rendering functions.
"""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

from .types import DataPoint


class BaseRenderer:
    """
    Base class for data renderers with common drawing utilities.

    Subclasses should implement match_data() and render_on_frame().
    """

    def draw_text(
        self,
        frame: np.ndarray,
        text: str,
        position: Tuple[int, int],
        *,
        font_scale: float = 1.0,
        color: Tuple[int, int, int] = (255, 255, 255),
        thickness: int = 2,
        bg_color: Tuple[int, int, int] | None = (0, 0, 0),
    ) -> np.ndarray:
        """
        Draw text on frame with optional background.

        Args:
            frame: Video frame
            text: Text to draw
            position: (x, y) position for text
            font_scale: Font size scale
            color: Text color (BGR)
            thickness: Text thickness
            bg_color: Background color (BGR), None for no background

        Returns:
            Frame with text drawn
        """
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Get text size for background
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

        x, y = position

        # Draw background rectangle
        if bg_color is not None:
            padding = 5
            cv2.rectangle(
                frame,
                (x - padding, y - text_h - padding),
                (x + text_w + padding, y + baseline + padding),
                bg_color,
                -1,
            )

        # Draw text
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

        return frame

    def draw_value_overlay(
        self,
        frame: np.ndarray,
        label: str,
        value: str,
        position: Tuple[int, int] = (20, 50),
        *,
        font_scale: float = 0.8,
    ) -> np.ndarray:
        """
        Draw label-value pair as overlay.

        Args:
            frame: Video frame
            label: Data label
            value: Data value as string
            position: Top-left position
            font_scale: Font size

        Returns:
            Frame with overlay
        """
        text = f"{label}: {value}"
        return self.draw_text(
            frame,
            text,
            position,
            font_scale=font_scale,
            color=(0, 255, 0),  # Green
            bg_color=(0, 0, 0),  # Black background
        )

    def draw_graph(
        self,
        frame: np.ndarray,
        values: List[float],
        position: Tuple[int, int],
        size: Tuple[int, int],
        *,
        color: Tuple[int, int, int] = (0, 255, 0),
        line_thickness: int = 2,
    ) -> np.ndarray:
        """
        Draw a simple line graph on frame.

        Args:
            frame: Video frame
            values: Data values to plot
            position: (x, y) top-left corner
            size: (width, height) of graph area
            color: Line color (BGR)
            line_thickness: Line thickness

        Returns:
            Frame with graph
        """
        if not values:
            return frame

        x, y = position
        width, height = size

        # Draw background
        cv2.rectangle(
            frame,
            (x, y),
            (x + width, y + height),
            (50, 50, 50),
            -1,
        )

        # Normalize values to graph height
        min_val = min(values)
        max_val = max(values)
        value_range = max_val - min_val if max_val > min_val else 1.0

        points = []
        for i, val in enumerate(values):
            px = x + int((i / max(len(values) - 1, 1)) * width)
            normalized = (val - min_val) / value_range
            py = y + height - int(normalized * height)
            points.append((px, py))

        # Draw polyline
        if len(points) > 1:
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(
                frame,
                [pts],
                isClosed=False,
                color=color,
                thickness=line_thickness,
            )

        return frame


class TextRenderer(BaseRenderer):
    """
    Simple text-based renderer for displaying numeric data values.

    Example renderer implementation showing the DataRenderer protocol.
    """

    def __init__(
        self,
        data_series,
        label: str,
        value_column: str,
        position: Tuple[int, int] = (20, 50),
    ):
        """
        Initialize text renderer.

        Args:
            data_series: DataFrame with timestamp_ms and data columns
            label: Display label for the data
            value_column: Column name to render
            position: Screen position for text
        """
        self.data_series = data_series
        self.label = label
        self.value_column = value_column
        self.position = position

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[DataPoint]:
        """Find matching data points using nearest matching."""
        from .matching import match_data_to_timestamp

        return match_data_to_timestamp(
            self.data_series,
            timestamp_ms,
            tolerance_ms=tolerance_ms,
            method="nearest",
        )

    def render_on_frame(
        self,
        frame: np.ndarray,
        data: List[DataPoint],
    ) -> np.ndarray:
        """Render data as text overlay."""
        if not data:
            value_str = "N/A"
        else:
            value = data[0].data.get(self.value_column, "N/A")
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)

        return self.draw_value_overlay(
            frame,
            self.label,
            value_str,
            self.position,
        )
