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

# Import renderers
from .renderers import (
    BaseDataRenderer,
    SpeedRenderer,
    TargetRenderer,
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
    # Renderers
    "BaseDataRenderer",
    "SpeedRenderer",
    "TargetRenderer",
]


