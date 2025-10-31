"""
Data renderers for repro module.

Each renderer handles one type of data and renders it onto video frames.

Available renderers:
- BaseDataRenderer: Abstract base class with common matching strategies
- SpeedRenderer: Render vehicle speed data
- TargetRenderer: Render 3D object detections with projection

Example usage:
    >>> from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer
    >>>
    >>> # Create renderers
    >>> speed_renderer = SpeedRenderer(
    ...     data_path="input/speed.jsonl",
    ...     position=(30, 60),
    ...     tolerance_ms=5000.0
    ... )
    >>>
    >>> target_renderer = TargetRenderer(
    ...     data_path="input/adb_targets.jsonl",
    ...     calibration_path="camera_calibration.yaml",
    ...     tolerance_ms=50.0
    ... )
    >>>
    >>> # Render on frame
    >>> frame = cv2.imread("frame.png")
    >>> timestamp_ms = 1761525000000.0
    >>> frame = speed_renderer.render(frame, timestamp_ms)
    >>> frame = target_renderer.render(frame, timestamp_ms)
"""

from .base import BaseDataRenderer
from .speed_renderer import SpeedRenderer
from .target_renderer import TargetRenderer

__all__ = [
    'BaseDataRenderer',
    'SpeedRenderer',
    'TargetRenderer',
]
