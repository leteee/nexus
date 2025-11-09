"""
Data replay visualization module for Nexus.

Provides utilities for replaying time-series data synchronized with video:
- Video frame extraction and composition
- Time-based data matching
- Abstract rendering interface for data visualization
- Modular renderers for different data types
- Simple renderer registration system

Main components:
    - types: DataRenderer base class, data structures, utility functions
    - video: extract_frames(), compose_video(), render_all_frames()
    - datagen: Timeline/speed/ADB data generators
    - renderers: SpeedRenderer, TargetRenderer, BaseDataRenderer

Example:
    >>> from nexus.contrib.repro import render_all_frames, list_renderers, render
    >>>
    >>> # List available renderers
    >>> renderers = list_renderers()
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
    >>> from nexus.contrib.repro import render, BaseDataRenderer
    >>>
    >>> @render("my_custom")
    >>> class MyCustomRenderer(BaseDataRenderer):
    ...     def render(self, frame, timestamp_ms):
    ...         return frame
"""

from __future__ import annotations

from typing import Dict, Type
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Simple Renderer Registry
# ============================================================================

# Global renderer registry: {name: renderer_class}
_RENDERER_REGISTRY: Dict[str, Type] = {}


def render(name: str):
    """
    Decorator to register a renderer class.

    Usage:
        >>> from nexus.contrib.repro import render, BaseDataRenderer
        >>>
        >>> @render("speed")
        >>> class SpeedRenderer(BaseDataRenderer):
        ...     def render(self, frame, timestamp_ms):
        ...         # Draw speed on frame
        ...         return frame

    Args:
        name: Unique name for the renderer (e.g., "speed", "target")

    Returns:
        Decorator function that registers the class
    """
    def decorator(cls: Type) -> Type:
        if name in _RENDERER_REGISTRY:
            logger.warning(f"Renderer '{name}' is already registered, overwriting")

        _RENDERER_REGISTRY[name] = cls
        logger.debug(f"Registered renderer: {name} -> {cls.__name__}")
        return cls

    return decorator


def get_renderer(name: str) -> Type:
    """
    Get a registered renderer class by name.

    Args:
        name: Renderer name

    Returns:
        Renderer class

    Raises:
        KeyError: If renderer not found
    """
    if name not in _RENDERER_REGISTRY:
        available = ", ".join(sorted(_RENDERER_REGISTRY.keys()))
        raise KeyError(
            f"Renderer '{name}' not found. Available renderers: {available}"
        )
    return _RENDERER_REGISTRY[name]


def list_renderers() -> Dict[str, Type]:
    """
    Get all registered renderers.

    Returns:
        Dictionary mapping renderer names to classes
    """
    return _RENDERER_REGISTRY.copy()

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
    # Renderer registration
    "render",
    "get_renderer",
    "list_renderers",
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


