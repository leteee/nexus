# src/nexus/contrib/repro/common/__init__.py

"""
Common utilities for the Repro module, including sensor data management, I/O, and drawing tools.
"""

from .sensor_manager import SensorDataManager, SensorStream
from .io import load_frame_timestamps, load_jsonl, save_jsonl
from .utils import get_video_metadata
from .time_utils import (
    DEFAULT_TZ,
    TimeProvider,
    make_tz,
    parse_timestamp,
    format_timestamp,
    format_duration,
    format_timecode,
)
from .text_renderer import (
    draw_textbox,
    TextboxConfig,
    FontConfig,
    PanelConfig,
    PositionConfig,
    AnchorPoint,
)


__all__ = [
    # sensor_manager
    "SensorDataManager",
    "SensorStream",
    # io
    "load_frame_timestamps",
    "load_jsonl",
    "save_jsonl",
    # time_utils
    "DEFAULT_TZ",
    "TimeProvider",
    "make_tz",
    "parse_timestamp",
    "format_timestamp",
    "format_duration",
    "format_timecode",
    # utils
    "get_video_metadata",
    # text_renderer
    "draw_textbox",
    "TextboxConfig",
    "FontConfig",
    "PanelConfig",
    "PositionConfig",
    "AnchorPoint",
]
