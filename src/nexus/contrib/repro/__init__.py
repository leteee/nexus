"""Repro: video data replay and temporal sensor visualization (Nexus 2.0).

This pack is optional.  Install ``nexus[repro]`` for pandas-free video and
sensor tooling; the Nexus core does not import anything from this package.
"""

from __future__ import annotations

from .camera import DEFAULT_CAMERA_PATH, CameraModel, ProjectedTarget
from .datagen import (
    DEFAULT_PROFILES,
    MAX_ANGLE_H,
    MAX_ANGLE_V,
    TARGET_DIMS,
    SpeedProfile,
    TargetType,
    calculate_edge_angles,
    generate_adb_targets,
    generate_driving_video,
    generate_speed,
    generate_timeline,
    generate_timeline_from_range,
    save_timeline_csv,
)
from .errors import (
    CameraError,
    MissingFrameError,
    OutputExistsError,
    RendererError,
    ReproError,
    SensorDataError,
    TimelineError,
    VideoError,
)
from .io import load_jsonl, save_jsonl
from .models import (
    ComposeResult,
    ExtractResult,
    FrameSetResult,
    RendererSpec,
    RenderRequest,
    RenderResult,
    SensorMatch,
    SensorSpec,
    VideoProbe,
)
from .render import ReplayPipeline
from .renderers import (
    FrameInfoRenderer,
    RenderContext,
    Renderer,
    RendererRegistry,
    SpeedRenderer,
    TargetRenderer,
    default_renderer_registry,
    register_renderer,
)
from .sensors import SensorReader, SensorStore
from .text import TextboxStyle, draw_textbox
from .time import (
    DEFAULT_TZ,
    TimeProvider,
    format_duration,
    format_timecode,
    format_timestamp,
    parse_timestamp,
)
from .timeline import FramePattern, FrameTimeline
from .video import (
    atomic_output_dir,
    blank_frames,
    compose_video,
    extract_frames,
    probe_video,
)

__version__ = "2.0.0"

__all__ = [
    "CameraModel",
    "ProjectedTarget",
    "DEFAULT_CAMERA_PATH",
    "DEFAULT_PROFILES",
    "MAX_ANGLE_H",
    "MAX_ANGLE_V",
    "TARGET_DIMS",
    "SpeedProfile",
    "TargetType",
    "calculate_edge_angles",
    "generate_adb_targets",
    "generate_driving_video",
    "generate_speed",
    "generate_timeline",
    "generate_timeline_from_range",
    "save_timeline_csv",
    "CameraError",
    "MissingFrameError",
    "OutputExistsError",
    "RendererError",
    "ReproError",
    "SensorDataError",
    "TimelineError",
    "VideoError",
    "load_jsonl",
    "save_jsonl",
    "ComposeResult",
    "ExtractResult",
    "FrameSetResult",
    "RendererSpec",
    "RenderRequest",
    "RenderResult",
    "SensorMatch",
    "SensorSpec",
    "VideoProbe",
    "ReplayPipeline",
    "FrameInfoRenderer",
    "RenderContext",
    "Renderer",
    "RendererRegistry",
    "SpeedRenderer",
    "TargetRenderer",
    "default_renderer_registry",
    "register_renderer",
    "SensorReader",
    "SensorStore",
    "TextboxStyle",
    "draw_textbox",
    "DEFAULT_TZ",
    "TimeProvider",
    "format_duration",
    "format_timecode",
    "format_timestamp",
    "parse_timestamp",
    "FramePattern",
    "FrameTimeline",
    "atomic_output_dir",
    "blank_frames",
    "compose_video",
    "extract_frames",
    "probe_video",
    "__version__",
]
