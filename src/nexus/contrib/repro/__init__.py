"""
Data replay visualization module for Nexus.

Provides utilities for replaying time-series data synchronized with video:
- Video frame extraction and composition
- Time-based data matching
- Abstract rendering interface for data visualization
- Modular renderers for different data types
- High-performance parallel processing (3-8x speedup)

Main components:
    - types: DataRenderer base class, data structures, utility functions
    - video: extract_frames(), compose_video(), render_all_frames()
    - video_parallel: render_all_frames_parallel() - High-performance parallel version
    - video_benchmark: Performance profiling and comparison tools
    - datagen: Timeline/speed/ADB data generators
    - renderers: SpeedRenderer, TargetRenderer, FrameInfoRenderer

Performance:
    - Sequential (optimized): 2.5-3x faster than original
    - Parallel processing: 3-8x faster than sequential (depending on CPU cores)
    - See performance_optimization.md for detailed guide

Example (Sequential):
    >>> from nexus.contrib.repro import render_all_frames
    >>> from nexus.contrib.repro.renderers import SpeedRenderer, TargetRenderer
    >>>
    >>> # Use renderer classes directly
    >>> renderer_configs = [
    ...     {"class": "nexus.contrib.repro.renderers.SpeedRenderer",
    ...      "sensor": "speed_sensor", "kwargs": {...}},
    ...     {"class": "nexus.contrib.repro.renderers.TargetRenderer",
    ...      "sensor": "target_sensor", "kwargs": {...}}
    ... ]
    >>> render_all_frames("frames/", "output/", "timestamps.csv",
    ...                   sensor_configs, renderer_configs, ctx=ctx)

Example (Parallel - Recommended for >100 frames):
    >>> from nexus.contrib.repro.video_parallel import render_all_frames_parallel
    >>>
    >>> # Drop-in replacement with 3-8x speedup
    >>> render_all_frames_parallel(
    ...     "frames/", "output/", "timestamps.csv",
    ...     sensor_configs, renderer_configs, ctx=ctx,
    ...     num_workers=8  # Use 8 CPU cores (default: all cores)
    ... )

Example (Benchmarking):
    >>> from nexus.contrib.repro.video_benchmark import compare_render_methods
    >>>
    >>> results = compare_render_methods(
    ...     frames_dir, output_base, timestamps_path,
    ...     sensor_configs, renderer_configs, ctx,
    ...     methods=["sequential", "parallel"],
    ...     num_workers=8
    ... )
    >>> print(results)
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

# Standard video processing
from .video import (
    extract_frames,
    compose_video,
    render_all_frames,
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


