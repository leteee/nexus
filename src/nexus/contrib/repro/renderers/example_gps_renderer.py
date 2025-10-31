"""
Example: Custom GPS Renderer

This example shows how to create a custom renderer by extending BaseDataRenderer.
Users can easily add new data types by implementing their own renderer class.

Steps:
1. Inherit from BaseDataRenderer
2. Implement render() method
3. Configure in pipeline YAML

Data format example (gps.jsonl):
{"timestamp_ms": 1759284000000.0, "lat": 39.9042, "lon": 116.4074, "altitude": 50.2}
{"timestamp_ms": 1759284001000.0, "lat": 39.9043, "lon": 116.4075, "altitude": 50.3}
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

from nexus.contrib.repro.renderers import BaseDataRenderer


class GPSRenderer(BaseDataRenderer):
    """
    Render GPS coordinates on video frames.

    Example custom renderer showing how users can extend the system.
    """

    def __init__(
        self,
        data_path: Path | str,
        position: Tuple[int, int] = (20, 100),
        tolerance_ms: float = 1000.0,
        font_scale: float = 0.6,
        color: Tuple[int, int, int] = (255, 255, 0),  # Cyan
    ):
        """
        Args:
            data_path: Path to GPS JSONL file
            position: (x, y) position for text
            tolerance_ms: Matching tolerance (default 1s, nearest strategy)
            font_scale: Font size
            color: Text color in BGR
        """
        super().__init__(
            data_path=data_path,
            tolerance_ms=tolerance_ms,
            match_strategy="nearest",
        )

        self.position = position
        self.font_scale = font_scale
        self.color = color

    def render(self, frame: np.ndarray, timestamp_ms: float) -> np.ndarray:
        """Render GPS data on frame."""
        # Match GPS data using base class method
        matched = self.match_data(timestamp_ms)

        if not matched:
            return frame

        gps_data = matched[0]

        # Format GPS text
        lat = gps_data.get("lat", 0.0)
        lon = gps_data.get("lon", 0.0)
        alt = gps_data.get("altitude", 0.0)

        lines = [
            f"GPS: {lat:.6f}°, {lon:.6f}°",
            f"Alt: {alt:.1f}m",
        ]

        # Draw text with background
        x, y = self.position
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2
        line_height = 30

        for i, text in enumerate(lines):
            current_y = y + i * line_height

            # Get text size
            (text_w, text_h), baseline = cv2.getTextSize(
                text, font, self.font_scale, thickness
            )

            # Draw background
            padding = 5
            cv2.rectangle(
                frame,
                (x - padding, current_y - text_h - padding),
                (x + text_w + padding, current_y + baseline + padding),
                (0, 0, 0),
                -1,
            )

            # Draw text
            cv2.putText(
                frame,
                text,
                (x, current_y),
                font,
                self.font_scale,
                self.color,
                thickness,
                cv2.LINE_AA,
            )

        return frame


# =============================================================================
# Usage Example
# =============================================================================

def example_usage():
    """
    Example showing how to use multiple renderers together.

    This demonstrates the extensible architecture:
    1. Import existing renderers
    2. Create custom renderers
    3. Apply them sequentially to frames
    """
    from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer

    # Setup renderers
    speed_renderer = SpeedRenderer(
        data_path="input/speed.jsonl",
        position=(30, 60),
        tolerance_ms=5000.0,
    )

    target_renderer = TargetRenderer(
        data_path="input/adb_targets.jsonl",
        calibration_path="camera_calibration.yaml",
        tolerance_ms=50.0,
    )

    gps_renderer = GPSRenderer(
        data_path="input/gps.jsonl",
        position=(20, 100),
        tolerance_ms=1000.0,
    )

    # Process a single frame
    frame = cv2.imread("temp/frames/frame_0000.png")
    timestamp_ms = 1761525000000.0

    # Apply all renderers (pipeline pattern)
    frame = speed_renderer.render(frame, timestamp_ms)
    frame = target_renderer.render(frame, timestamp_ms)
    frame = gps_renderer.render(frame, timestamp_ms)

    # Save result
    cv2.imwrite("output/rendered_frame.png", frame)


# =============================================================================
# Configuration-driven Usage (with dynamic class loading)
# =============================================================================

def load_renderer_from_config(config: dict):
    """
    Dynamically load renderer class from config.

    This is how the Data Renderer Plugin would instantiate renderers.

    Args:
        config: Dict with 'class' (full module path) and 'kwargs'

    Example config:
        {
            "class": "nexus.contrib.repro.renderers.SpeedRenderer",
            "kwargs": {
                "data_path": "input/speed.jsonl",
                "position": [20, 50],
                "tolerance_ms": 5000
            }
        }
    """
    import importlib

    # Parse class path
    class_path = config["class"]
    module_path, class_name = class_path.rsplit(".", 1)

    # Import module and get class
    module = importlib.import_module(module_path)
    renderer_class = getattr(module, class_name)

    # Instantiate with kwargs
    kwargs = config.get("kwargs", {})
    return renderer_class(**kwargs)


def example_config_driven_usage():
    """
    Example using configuration-driven renderer loading.

    This matches the YAML configuration format you specified.
    """
    # Configuration (would come from YAML)
    renderer_configs = [
        {
            "class": "nexus.contrib.repro.renderers.SpeedRenderer",
            "kwargs": {
                "data_path": "input/speed.jsonl",
                "position": (20, 50),
                "tolerance_ms": 5000,
            }
        },
        {
            "class": "nexus.contrib.repro.renderers.TargetRenderer",
            "kwargs": {
                "data_path": "input/adb_targets.jsonl",
                "calibration_path": "camera_calibration.yaml",
                "tolerance_ms": 50,
            }
        },
        {
            "class": "nexus.contrib.repro.renderers.example_gps_renderer.GPSRenderer",
            "kwargs": {
                "data_path": "input/gps.jsonl",
                "position": (20, 100),
            }
        },
    ]

    # Load all renderers
    renderers = [load_renderer_from_config(cfg) for cfg in renderer_configs]

    # Process frame
    frame = cv2.imread("temp/frames/frame_0000.png")
    timestamp_ms = 1761525000000.0

    # Apply all renderers
    for renderer in renderers:
        frame = renderer.render(frame, timestamp_ms)

    cv2.imwrite("output/rendered_frame.png", frame)


if __name__ == "__main__":
    print("Example GPS Renderer")
    print("=" * 60)
    print()
    print("This demonstrates how to create custom renderers:")
    print("1. Inherit from BaseDataRenderer")
    print("2. Implement render(frame, timestamp_ms)")
    print("3. Use built-in match_data() for time matching")
    print()
    print("See the GPSRenderer class above for a complete example.")
