# src/nexus/contrib/repro/common/__init__.py

"""
Common utilities for the Repro module, including sensor data management, I/O, and drawing tools.
"""

from .sensor_manager import SensorDataManager, SensorStream
from .io import load_frame_timestamps, load_jsonl, save_jsonl
from .utils import get_video_metadata
from .time_utils import (
    DEFAULT_TIMEZONE,
    parse_time_string,
    parse_time_value,
    timestamp_to_datetime,
    timestamp_to_string,
    format_duration_ms,
    get_current_timestamp_ms,
    create_timezone,
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
    "DEFAULT_TIMEZONE",
    "parse_time_string",
    "parse_time_value",
    "timestamp_to_datetime",
    "timestamp_to_string",
    "format_duration_ms",
    "get_current_timestamp_ms",
    "create_timezone",
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
