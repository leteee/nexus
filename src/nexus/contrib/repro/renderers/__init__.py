"""
Data renderers for repro module.

Each renderer handles one type of data and renders it onto video frames.

Available renderers:
- SpeedRenderer: Render vehicle speed data
- TargetRenderer: Render 3D object detections with projection
- FrameInfoRenderer: Render frame metadata (frame ID and timestamp)

Example usage:
    >>> from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer, FrameInfoRenderer
    >>>
    >>> # Create renderers
    >>> frame_info = FrameInfoRenderer(
    ...     ctx=ctx,
    ...     position=(10, 30),
    ...     format="datetime"
    ... )
    >>>
    >>> speed_renderer = SpeedRenderer(
    ...     ctx=ctx,
    ...     sensor="speed_sensor",
    ... )
    >>>
    >>> target_renderer = TargetRenderer(
    ...     ctx=ctx,
    ...     sensor="target_sensor",
    ...     calibration_path="camera_calibration.yaml",
    ... )
    >>>
    >>> # In the main loop, you would get data and pass it to the renderer
    >>> data = {"speed": 60.0, "snapshot_time_ms": 1000}
    >>> frame = speed_renderer.render(frame, data)
"""

from .speed_renderer import SpeedRenderer
from .target_renderer import TargetRenderer
from .frame_info_renderer import FrameInfoRenderer

__all__ = [
    'SpeedRenderer',
    'TargetRenderer',
    'FrameInfoRenderer',
]
