"""
Data replay visualization module for Nexus.

Provides utilities for replaying time-series data synchronized with video:
- Video frame extraction and composition
- Time-based data matching
- Abstract rendering interface for data visualization
- Modular renderers for different data types

Main components:
    - types: DataRenderer base class, data structures, utility functions
    - video: extract_frames(), compose_video()
    - datagen: Timeline/speed/ADB data generators
    - renderers: SpeedRenderer, TargetRenderer, BaseDataRenderer

Example:
    >>> from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer
    >>> from nexus.contrib.repro.video import extract_frames, compose_video
    >>>
    >>> # Extract frames
    >>> metadata = extract_frames("input.mp4", "frames/")
    >>>
    >>> # Setup renderers
    >>> speed = SpeedRenderer("speed.jsonl", position=(30, 60))
    >>> target = TargetRenderer("targets.jsonl", "calibration.yaml")
    >>>
    >>> # Render frames
    >>> for frame_path in frame_paths:
    ...     frame = cv2.imread(frame_path)
    ...     frame = speed.render(frame, timestamp_ms)
    ...     frame = target.render(frame, timestamp_ms)
    ...     cv2.imwrite(output_path, frame)
    >>>
    >>> # Compose video
    >>> compose_video("rendered_frames/", "output.mp4", fps=30.0)
"""

# Core types
from .types import (
    DataRenderer,
    VideoMetadata,
)

# I/O utilities
from .io import (
    load_frame_timestamps,
    load_jsonl,
    save_jsonl,
)

# Video processing
from .video import extract_frames, compose_video, render_all_frames

# Utilities
from .utils import (
    parse_time_string,
    parse_time_value,
    get_video_metadata,
)

# Data generation utilities
from .datagen import (
    generate_timeline_with_jitter,
    generate_speed_data_event_driven,
    generate_adb_target_data,
    save_timeline_csv,
    SpeedProfile,
)

__all__ = [
    # Types
    "DataRenderer",
    "VideoMetadata",
    # I/O utilities
    "load_frame_timestamps",
    "load_jsonl",
    "save_jsonl",
    # Video processing
    "extract_frames",
    "compose_video",
    "render_all_frames",
    # Utilities
    "parse_time_string",
    "parse_time_value",
    "get_video_metadata",
    # Data generation
    "generate_timeline_with_jitter",
    "generate_speed_data_event_driven",
    "generate_adb_target_data",
    "save_timeline_csv",
    "SpeedProfile",
]

