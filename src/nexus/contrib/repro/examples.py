"""
Example renderer implementations demonstrating DataRenderer pattern.

These serve as templates for users to create custom data visualizations.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np

from .types import DataRenderer, load_jsonl


class SimpleTextRenderer(DataRenderer):
    """
    Example: Render single numeric value as text overlay.

    Use case: Display speed, temperature, pressure, etc.

    JSONL format:
        {"timestamp_ms": 0.0, "speed": 120.5}
        {"timestamp_ms": 50.0, "speed": 125.3}
    """

    def __init__(
        self,
        data_path: Path | str,
        value_key: str,
        label: str,
        position: tuple[int, int] = (20, 50),
    ):
        """
        Args:
            data_path: Path to JSONL data file
            value_key: Key to extract from data (e.g., 'speed')
            label: Display label (e.g., 'Speed')
            position: (x, y) screen position
        """
        self.value_key = value_key
        self.label = label
        self.position = position
        super().__init__(data_path)

    def load_data(self, data_path: Path) -> None:
        """Load JSONL data."""
        self.data = load_jsonl(data_path)

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """Find nearest data point within tolerance."""
        if not self.data:
            return []

        # Find closest timestamp
        closest = min(
            self.data,
            key=lambda d: abs(d["timestamp_ms"] - timestamp_ms),
        )

        # Check tolerance
        if abs(closest["timestamp_ms"] - timestamp_ms) <= tolerance_ms:
            return [closest]

        return []

    def render(self, frame: np.ndarray, data: List[dict]) -> np.ndarray:
        """Render value as text overlay."""
        if not data:
            value_str = "N/A"
        else:
            value = data[0].get(self.value_key, "N/A")
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)

        text = f"{self.label}: {value_str}"

        # Draw background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

        x, y = self.position
        padding = 5

        cv2.rectangle(
            frame,
            (x - padding, y - text_h - padding),
            (x + text_w + padding, y + baseline + padding),
            (0, 0, 0),  # Black background
            -1,
        )

        # Draw text
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            (0, 255, 0),  # Green text
            thickness,
            cv2.LINE_AA,
        )

        return frame


class MultiValueRenderer(DataRenderer):
    """
    Example: Render multiple values as overlays.

    Use case: Display dashboard with multiple sensors.

    JSONL format:
        {"timestamp_ms": 0.0, "speed": 120.5, "rpm": 3000, "gear": 3}
        {"timestamp_ms": 50.0, "speed": 125.3, "rpm": 3200, "gear": 3}
    """

    def __init__(
        self,
        data_path: Path | str,
        fields: List[tuple[str, str]],  # [(key, label), ...]
        start_position: tuple[int, int] = (20, 50),
        line_spacing: int = 40,
    ):
        """
        Args:
            data_path: Path to JSONL data file
            fields: List of (key, label) tuples to render
            start_position: Starting (x, y) position
            line_spacing: Vertical spacing between lines
        """
        self.fields = fields
        self.start_position = start_position
        self.line_spacing = line_spacing
        super().__init__(data_path)

    def load_data(self, data_path: Path) -> None:
        """Load JSONL data."""
        self.data = load_jsonl(data_path)

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """Find nearest data point."""
        if not self.data:
            return []

        closest = min(
            self.data,
            key=lambda d: abs(d["timestamp_ms"] - timestamp_ms),
        )

        if abs(closest["timestamp_ms"] - timestamp_ms) <= tolerance_ms:
            return [closest]

        return []

    def render(self, frame: np.ndarray, data: List[dict]) -> np.ndarray:
        """Render multiple values as stacked text."""
        if not data:
            return frame

        record = data[0]
        x, y = self.start_position

        for key, label in self.fields:
            value = record.get(key, "N/A")
            if isinstance(value, float):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)

            text = f"{label}: {value_str}"

            # Draw text with background
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            thickness = 2

            (text_w, text_h), baseline = cv2.getTextSize(
                text, font, font_scale, thickness
            )

            padding = 3
            cv2.rectangle(
                frame,
                (x - padding, y - text_h - padding),
                (x + text_w + padding, y + baseline + padding),
                (0, 0, 0),
                -1,
            )

            cv2.putText(
                frame,
                text,
                (x, y),
                font,
                font_scale,
                (0, 255, 255),  # Yellow text
                thickness,
                cv2.LINE_AA,
            )

            y += self.line_spacing

        return frame


class NestedDataRenderer(DataRenderer):
    """
    Example: Render nested/structured data from JSONL.

    Use case: GPS coordinates, sensor arrays, complex telemetry.

    JSONL format:
        {"timestamp_ms": 0.0, "gps": {"lat": 39.9042, "lon": 116.4074}, "altitude": 50.0}
        {"timestamp_ms": 50.0, "gps": {"lat": 39.9043, "lon": 116.4075}, "altitude": 51.0}
    """

    def __init__(
        self,
        data_path: Path | str,
        position: tuple[int, int] = (20, 50),
    ):
        self.position = position
        super().__init__(data_path)

    def load_data(self, data_path: Path) -> None:
        """Load JSONL data with nested structures."""
        self.data = load_jsonl(data_path)

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """Find nearest data point."""
        if not self.data:
            return []

        closest = min(
            self.data,
            key=lambda d: abs(d["timestamp_ms"] - timestamp_ms),
        )

        if abs(closest["timestamp_ms"] - timestamp_ms) <= tolerance_ms:
            return [closest]

        return []

    def render(self, frame: np.ndarray, data: List[dict]) -> np.ndarray:
        """Render GPS coordinates and altitude."""
        if not data:
            return frame

        record = data[0]
        gps = record.get("gps", {})
        lat = gps.get("lat", "N/A")
        lon = gps.get("lon", "N/A")
        alt = record.get("altitude", "N/A")

        # Format text
        lines = [
            f"GPS: {lat:.4f}, {lon:.4f}" if isinstance(lat, float) else "GPS: N/A",
            f"Alt: {alt:.1f}m" if isinstance(alt, float) else "Alt: N/A",
        ]

        x, y = self.position
        for i, text in enumerate(lines):
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            thickness = 2

            (text_w, text_h), baseline = cv2.getTextSize(
                text, font, font_scale, thickness
            )

            padding = 3
            cv2.rectangle(
                frame,
                (x - padding, y - text_h - padding),
                (x + text_w + padding, y + baseline + padding),
                (0, 0, 0),
                -1,
            )

            cv2.putText(
                frame,
                text,
                (x, y),
                font,
                font_scale,
                (255, 0, 255),  # Magenta
                thickness,
                cv2.LINE_AA,
            )

            y += 35

        return frame


class BackwardMatchRenderer(DataRenderer):
    """
    Renderer with backward-only time matching.

    Matches data points within tolerance_ms BEFORE the frame timestamp.
    Use case: Real-time telemetry where future data is not available.

    JSONL format:
        {"timestamp_ms": 1759284000000.0, "speed": 120.5}
        {"timestamp_ms": 1759284000100.0, "speed": 125.3}
    """

    def __init__(
        self,
        data_path: Path | str,
        value_key: str,
        label: str,
        position: tuple[int, int] = (20, 50),
        tolerance_ms: float = 100.0,
    ):
        """
        Args:
            data_path: Path to JSONL data file
            value_key: Key to extract from data (e.g., 'speed')
            label: Display label (e.g., 'Speed')
            position: (x, y) screen position
            tolerance_ms: Maximum backward time difference (default 100ms)
        """
        self.value_key = value_key
        self.label = label
        self.position = position
        self.tolerance_ms = tolerance_ms
        super().__init__(data_path)

    def load_data(self, data_path: Path) -> None:
        """Load JSONL data."""
        self.data = load_jsonl(data_path)

    def match_data(
        self,
        timestamp_ms: float,
        tolerance_ms: float = 50.0,
    ) -> List[dict]:
        """Find most recent data point within backward tolerance."""
        if not self.data:
            return []

        # Use instance tolerance if tolerance_ms is default
        effective_tolerance = self.tolerance_ms if tolerance_ms == 50.0 else tolerance_ms

        # Filter data points that are BEFORE or AT the frame timestamp
        candidates = [
            d for d in self.data
            if d["timestamp_ms"] <= timestamp_ms
        ]

        if not candidates:
            return []

        # Find the closest data point within tolerance (backward only)
        closest = max(candidates, key=lambda d: d["timestamp_ms"])
        time_diff = timestamp_ms - closest["timestamp_ms"]

        # Check if within tolerance
        if time_diff <= effective_tolerance:
            return [closest]

        return []

    def render(self, frame: np.ndarray, data: List[dict]) -> np.ndarray:
        """Render value as text overlay."""
        if not data:
            value_str = "N/A"
        else:
            value = data[0].get(self.value_key, "N/A")
            if isinstance(value, float):
                value_str = f"{value:.1f}"
            else:
                value_str = str(value)

        text = f"{self.label}: {value_str}"

        # Draw background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

        x, y = self.position
        padding = 8

        cv2.rectangle(
            frame,
            (x - padding, y - text_h - padding),
            (x + text_w + padding, y + baseline + padding),
            (0, 0, 0),  # Black background
            -1,
        )

        # Draw text
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            (0, 255, 0),  # Green text
            thickness,
            cv2.LINE_AA,
        )

        return frame

