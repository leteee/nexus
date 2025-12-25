"""
Data replay visualization module for Nexus.

Provides utilities for replaying time-series data synchronized with video:
- Video frame extraction and composition
- Time-based data matching
- Abstract rendering interface for data visualization
- Modular renderers for different data types

Main components:
    - types: DataRenderer base class, data structures, utility functions
    - video: extract_frames(), compose_video(), render_all_frames()
    - datagen: Timeline/speed/ADB data generators
    - renderers: SpeedRenderer, TargetRenderer, BaseDataRenderer

Example:
    >>> from nexus.contrib.repro import render_all_frames
    >>> from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer
    >>>
    >>> # Use renderer classes directly
    >>> renderer_configs = [
    ...     {"class": "nexus.contrib.repro.renderers.SpeedRenderer",
    ...      "kwargs": {"data_path": "speed.jsonl"}},
    ...     {"class": "nexus.contrib.repro.renderers.TargetRenderer",
    ...      "kwargs": {"data_path": "targets.jsonl"}}
    ... ]
    >>> render_all_frames("frames/", "output/", "timestamps.csv", renderer_configs)
    >>>
    >>> # Create custom renderer
    >>> from nexus.contrib.repro.renderers import BaseDataRenderer
    >>>
    >>> class MyCustomRenderer(BaseDataRenderer):
    ...     def render(self, frame, timestamp_ms):
    ...         return frame
"""

from __future__ import annotations

# Core types
from .types import (
    DataRenderer,
    VideoMetadata,
)

# I/O utilities
from .common.io import (
    load_frame_timestamps,
    load_jsonl,
    save_jsonl,
)

# Video processing
from .video import extract_frames, compose_video, render_all_frames

# Time utilities
from .common.time_utils import (
    DEFAULT_TIMEZONE,
    parse_time_string,
    parse_time_value,
    timestamp_to_datetime,
    timestamp_to_string,
    format_duration_ms,
    get_current_timestamp_ms,
    create_timezone,
)

# Video utilities
from .common.utils import get_video_metadata

# Data generation utilities
from .datagen import (
    generate_timeline_with_jitter,
    generate_speed_data_event_driven,
    generate_adb_target_data,
    save_timeline_csv,
    SpeedProfile,
)

# Import renderers
from .renderers import (
    SpeedRenderer,
    TargetRenderer,
    FrameInfoRenderer,
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
    # Time parsing utilities
    "DEFAULT_TIMEZONE",
    "parse_time_string",
    "parse_time_value",
    # Time formatting utilities
    "timestamp_to_datetime",
    "timestamp_to_string",
    "format_duration_ms",
    "get_current_timestamp_ms",
    "create_timezone",
    # Video metadata
    "get_video_metadata",
    # Data generation
    "generate_timeline_with_jitter",
    "generate_speed_data_event_driven",
    "generate_adb_target_data",
    "save_timeline_csv",
    "SpeedProfile",
    # Renderers
    "SpeedRenderer",
    "TargetRenderer",
    "FrameInfoRenderer",
]


