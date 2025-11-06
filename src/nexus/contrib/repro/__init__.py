"""
Data replay visualization module for Nexus.

Provides utilities for replaying time-series data synchronized with video:
- Video frame extraction and composition
- Time-based data matching
- Abstract rendering interface for data visualization
- Modular renderers for different data types
- Unified execution unit framework for renderers

Main components:
    - types: DataRenderer base class, data structures, utility functions
    - video: extract_frames(), compose_video(), render_all_frames()
    - datagen: Timeline/speed/ADB data generators
    - renderers: SpeedRenderer, TargetRenderer, BaseDataRenderer
    - Execution units: Unified framework for renderer registration and execution

Example:
    >>> from nexus.contrib.repro import render_all_frames
    >>> from nexus.core.execution_units import list_units
    >>>
    >>> # List available renderers
    >>> renderers = list_units("renderer")
    >>> print(f"Available: {list(renderers.keys())}")
    >>>
    >>> # Use registered renderers by name
    >>> renderer_configs = [
    ...     {"name": "speed", "kwargs": {"data_path": "speed.jsonl"}},
    ...     {"name": "target", "kwargs": {"data_path": "targets.jsonl"}}
    ... ]
    >>> render_all_frames("frames/", "output/", "timestamps.csv", renderer_configs)
    >>>
    >>> # Create custom renderer
    >>> from nexus.core.execution_units import register_unit
    >>> from nexus.contrib.repro.renderers import BaseDataRenderer
    >>>
    >>> @register_unit("my_custom", unit_type="renderer")
    >>> class MyCustomRenderer(BaseDataRenderer):
    ...     def render(self, frame, timestamp_ms):
    ...         return frame
"""

# Ensure standard execution unit types are registered (plugin, renderer)
from nexus.core import standard_runners

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

# Import renderers to trigger registration with execution unit framework
# This ensures all built-in renderers are registered when module is imported
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


