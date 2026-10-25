"""Nexus 2.0 nodes for the optional repro pack."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from nexus.core.context import NodeContext
from nexus.core.registry import NodeInput, node

from .datagen import (
    SpeedProfile,
    generate_adb_targets,
    generate_driving_video,
    generate_speed,
    generate_timeline,
    generate_timeline_from_range,
    save_timeline_csv,
)
from .io import save_jsonl
from .models import RendererSpec, RenderRequest, SensorSpec
from .render import ReplayPipeline
from .time import parse_timestamp
from .timeline import FrameTimeline
from .video import blank_frames, compose_video, extract_frames, probe_video

logger = logging.getLogger(__name__)

TimeValue = str | float | datetime | None
RequiredTime = str | float | datetime


def _resolve_video(ctx: NodeContext, value: str) -> Path:
    expanded = Path(os.path.expandvars(os.path.expanduser(value)))
    path = expanded if expanded.is_absolute() else ctx.workdir / expanded
    if any(character in str(path) for character in "*?[]"):
        matches = sorted(path.parent.glob(path.name))
        if not matches:
            raise FileNotFoundError(f"no video matched '{value}' (resolved to {path})")
        return matches[0]
    return path.resolve()


def _optional_time(value: TimeValue) -> float | None:
    if value is None:
        return None
    return float(parse_timestamp(value))


def _time_bounds(start: RequiredTime, end: RequiredTime) -> tuple[float, float]:
    start_ms = float(parse_timestamp(start))
    end_ms = float(parse_timestamp(end))
    if end_ms <= start_ms:
        raise ValueError("end_time must be after start_time")
    return start_ms, end_ms


class VideoSplitInput(NodeInput):
    video_path: str = Field(description="Input video path or glob pattern.")
    output_dir: str = Field(default="temp/frames", description="Directory for extracted PNG frames.")
    frame_pattern: str = Field(default="frame_{:06d}.png")
    overwrite: bool = Field(default=False, description="Replace an existing output directory atomically.")
    progress: bool = True


@node(
    "repro.video.split",
    inputs=VideoSplitInput,
    tags=["repro", "video"],
    description="Extract all frames from a video into an image directory.",
)
def split_video(ctx: NodeContext, inputs: VideoSplitInput) -> dict[str, Any]:
    video_path = _resolve_video(ctx, inputs.video_path)
    result = extract_frames(
        video_path,
        ctx.path(inputs.output_dir),
        frame_pattern=inputs.frame_pattern,
        overwrite=inputs.overwrite,
        progress=inputs.progress,
    )
    return {
        "video_path": str(video_path),
        "frames_dir": str(result.output_dir),
        "total_frames": result.frame_count,
        "fps": result.probe.fps,
        "width": result.probe.width,
        "height": result.probe.height,
    }


class VideoComposeInput(NodeInput):
    frames_dir: str = Field(default="temp/frames")
    output_path: str = Field(default="output/repro.mp4")
    fps: float = Field(default=30.0, gt=0)
    frame_pattern: str = Field(default="frame_{:06d}.png")
    codec: str = Field(default="mp4v")
    start_time: TimeValue = Field(default=None, description="Optional clip start time.")
    end_time: TimeValue = Field(default=None, description="Optional clip end time.")
    timestamps_path: str | None = Field(default=None, description="Timeline CSV for time-based clipping.")
    start_frame: int | None = Field(default=None, ge=0)
    end_frame: int | None = Field(default=None, ge=0)
    overwrite: bool = Field(default=False)
    progress: bool = True


@node(
    "repro.video.compose",
    inputs=VideoComposeInput,
    tags=["repro", "video"],
    description="Compose frames into a video, optionally clipped by time or frame index.",
)
def compose_frames(ctx: NodeContext, inputs: VideoComposeInput) -> dict[str, Any]:
    start_frame = inputs.start_frame
    end_frame = inputs.end_frame
    if inputs.start_time is not None or inputs.end_time is not None:
        if not inputs.timestamps_path:
            raise ValueError("timestamps_path is required when start_time/end_time are used")
        timeline = FrameTimeline.from_csv(ctx.path(inputs.timestamps_path))
        start_frame, end_frame = timeline.frame_range_for_time(
            _optional_time(inputs.start_time),
            _optional_time(inputs.end_time),
        )
    result = compose_video(
        ctx.path(inputs.frames_dir),
        ctx.path(inputs.output_path),
        fps=inputs.fps,
        frame_pattern=inputs.frame_pattern,
        codec=inputs.codec,
        start_frame=start_frame,
        end_frame=end_frame,
        overwrite=inputs.overwrite,
        progress=inputs.progress,
    )
    return {
        "output_path": str(result.output_path),
        "frame_count": result.frame_count,
        "fps": result.fps,
        "width": result.width,
        "height": result.height,
    }


class RenderFramesInput(NodeInput):
    frames_dir: str = Field(default="temp/frames")
    timeline: str = Field(default="temp/timeline.csv")
    output_dir: str = Field(default="temp/rendered")
    sensors: dict[str, SensorSpec] = Field(default_factory=dict)
    renderers: list[RendererSpec] = Field(default_factory=list)
    start_time: TimeValue = None
    end_time: TimeValue = None
    start_frame: int | None = Field(default=None, ge=0)
    end_frame: int | None = Field(default=None, ge=0)
    workers: int = Field(default=1, ge=1, le=256)
    overwrite: bool = Field(default=False)
    missing_frame: Literal["fail", "skip"] = "fail"
    frame_pattern: str = Field(default="frame_{:06d}.png")
    progress: bool = True


@node(
    "repro.render.frames",
    inputs=RenderFramesInput,
    tags=["repro", "rendering"],
    description="Render typed sensor overlays onto frames using the replay pipeline.",
)
def render_frames(ctx: NodeContext, inputs: RenderFramesInput) -> dict[str, Any]:
    sensors = {
        name: spec.model_copy(update={"path": ctx.path(spec.path)})
        for name, spec in inputs.sensors.items()
    }
    renderers: list[RendererSpec] = []
    for spec in inputs.renderers:
        if not spec.enabled:
            continue
        config = dict(spec.config)
        camera = config.get("camera")
        if isinstance(camera, str) and camera != "auto":
            camera_path = ctx.path(camera)
            if not camera_path.exists():
                project_candidate = ctx.project_path(camera)
                if project_candidate.exists():
                    camera_path = project_candidate
            config["camera"] = str(camera_path)
        renderers.append(spec.model_copy(update={"config": config}))

    request = RenderRequest(
        frames_dir=ctx.path(inputs.frames_dir),
        timeline=ctx.path(inputs.timeline),
        output_dir=ctx.path(inputs.output_dir),
        sensors=sensors,
        renderers=renderers,
        start_ms=_optional_time(inputs.start_time),
        end_ms=_optional_time(inputs.end_time),
        start_frame=inputs.start_frame,
        end_frame=inputs.end_frame,
        workers=inputs.workers,
        overwrite=inputs.overwrite,
        missing_frame=inputs.missing_frame,
        frame_pattern=inputs.frame_pattern,
        progress=inputs.progress,
    )
    result = ReplayPipeline().render(request)
    return {
        "output_dir": str(result.output_dir),
        "frame_count": result.frame_count,
        "rendered_count": result.rendered_count,
        "skipped_count": result.skipped_count,
        "duration_ms": result.duration_ms,
        "renderers": list(result.renderers),
        "sensors": list(result.sensors),
    }


class BlankFramesInput(NodeInput):
    timestamps_path: str
    output_dir: str = Field(default="temp/frames")
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    color: tuple[int, int, int] = (0, 0, 0)
    frame_pattern: str = Field(default="frame_{:06d}.png")
    overwrite: bool = Field(default=False)
    progress: bool = True


@node(
    "repro.video.blank_frames",
    inputs=BlankFramesInput,
    tags=["repro", "video", "generation"],
    description="Generate solid-color frames for every entry in a timeline.",
)
def generate_blank_frames(ctx: NodeContext, inputs: BlankFramesInput) -> dict[str, Any]:
    timeline = FrameTimeline.from_csv(ctx.path(inputs.timestamps_path))
    result = blank_frames(
        timeline,
        ctx.path(inputs.output_dir),
        width=inputs.width,
        height=inputs.height,
        color=inputs.color,
        frame_pattern=inputs.frame_pattern,
        overwrite=inputs.overwrite,
        progress=inputs.progress,
    )
    return {
        "output_dir": str(result.output_dir),
        "count": result.frame_count,
        "width": result.width,
        "height": result.height,
    }


class SyntheticVideoInput(NodeInput):
    output_path: str = Field(default="input/synthetic_driving.mp4")
    start_time: RequiredTime
    end_time: RequiredTime
    fps: float = Field(default=30.0, gt=0)
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    speed_kmh: float = Field(default=60.0, ge=0)
    random_seed: int | None = None
    overwrite: bool = Field(default=False)
    progress: bool = True


@node(
    "repro.datagen.video",
    inputs=SyntheticVideoInput,
    tags=["repro", "video", "generation"],
    description="Generate a synthetic forward-driving video for testing.",
)
def generate_synthetic_video(ctx: NodeContext, inputs: SyntheticVideoInput) -> dict[str, Any]:
    start_ms, end_ms = _time_bounds(inputs.start_time, inputs.end_time)
    probe = generate_driving_video(
        ctx.path(inputs.output_path),
        start_time=start_ms,
        end_time=end_ms,
        fps=inputs.fps,
        width=inputs.width,
        height=inputs.height,
        speed_kmh=inputs.speed_kmh,
        random_seed=inputs.random_seed,
        overwrite=inputs.overwrite,
        progress=inputs.progress,
    )
    return {
        "output_path": str(probe.source),
        "fps": probe.fps,
        "total_frames": probe.total_frames,
        "width": probe.width,
        "height": probe.height,
        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,
    }


class TimelineInput(NodeInput):
    video_path: str | None = Field(default=None, description="Video used to infer fps.")
    fps: float | None = Field(default=None, gt=0)
    start_time: RequiredTime
    end_time: RequiredTime
    jitter_ms: int = Field(default=2, ge=0, le=100)
    output_path: str = "temp/timeline.csv"
    random_seed: int | None = None


@node(
    "repro.datagen.timeline",
    inputs=TimelineInput,
    tags=["repro", "generation"],
    description="Generate a frame timeline CSV with realistic timestamp jitter.",
)
def generate_timeline_node(ctx: NodeContext, inputs: TimelineInput) -> dict[str, Any]:
    start_ms, end_ms = _time_bounds(inputs.start_time, inputs.end_time)
    if inputs.video_path:
        probe = probe_video(_resolve_video(ctx, inputs.video_path))
        fps = inputs.fps or probe.fps
    elif inputs.fps is not None:
        fps = inputs.fps
    else:
        raise ValueError("provide video_path or fps")

    records = generate_timeline(
        fps=fps,
        start_time=start_ms,
        end_time=end_ms,
        jitter_ms=inputs.jitter_ms,
        random_seed=inputs.random_seed,
    )
    output_path = ctx.path(inputs.output_path)
    save_timeline_csv(records, output_path)
    return {
        "timestamps_path": str(output_path),
        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,
        "fps": fps,
        "total_frames": len(records),
        "first_timestamp_ms": records[0]["timestamp_ms"],
        "last_timestamp_ms": records[-1]["timestamp_ms"],
    }


class TimelineFromRangeInput(NodeInput):
    start_time: str | datetime = "2025-10-27 00:00:00"
    end_time: str | datetime
    fps: float = Field(default=30.0, gt=0)
    output_path: str = "temp/timeline.csv"
    jitter_ms: int = Field(default=0, ge=0, le=100)
    random_seed: int | None = None


@node(
    "repro.timeline.from_range",
    inputs=TimelineFromRangeInput,
    tags=["repro", "generation"],
    description="Generate a timeline from a start/end time and fps.",
)
def generate_timeline_range(ctx: NodeContext, inputs: TimelineFromRangeInput) -> dict[str, Any]:
    records, start_ms, end_ms, total_frames = generate_timeline_from_range(
        start_time=inputs.start_time,
        end_time=inputs.end_time,
        fps=inputs.fps,
        jitter_ms=inputs.jitter_ms,
        random_seed=inputs.random_seed,
    )
    output_path = ctx.path(inputs.output_path)
    save_timeline_csv(records, output_path)
    return {
        "timestamps_path": str(output_path),
        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,
        "fps": inputs.fps,
        "total_frames": total_frames,
        "first_timestamp_ms": records[0]["timestamp_ms"],
        "last_timestamp_ms": records[-1]["timestamp_ms"],
    }


class SpeedInput(NodeInput):
    start_time: RequiredTime
    end_time: RequiredTime
    max_interval_s: float = Field(default=5.0, gt=0)
    change_threshold: float = Field(default=2.0, ge=0)
    output_path: str = "input/speed.jsonl"
    random_seed: int | None = None
    use_default_profile: bool = True
    custom_profiles: list[dict[str, Any]] | None = None


@node(
    "repro.datagen.speed",
    inputs=SpeedInput,
    tags=["repro", "generation"],
    description="Generate event-driven vehicle speed records as JSONL.",
)
def generate_speed_node(ctx: NodeContext, inputs: SpeedInput) -> dict[str, Any]:
    start_ms, end_ms = _time_bounds(inputs.start_time, inputs.end_time)
    profiles = None
    if not inputs.use_default_profile:
        if not inputs.custom_profiles:
            raise ValueError("custom_profiles is required when use_default_profile is false")
        profiles = [SpeedProfile(**profile) for profile in inputs.custom_profiles]
    records = generate_speed(
        start_time=start_ms,
        end_time=end_ms,
        profiles=profiles,
        max_interval_s=inputs.max_interval_s,
        change_threshold=inputs.change_threshold,
        random_seed=inputs.random_seed,
    )
    output_path = save_jsonl(records, ctx.path(inputs.output_path))
    speeds = [record["speed"] for record in records]
    return {
        "output_path": str(output_path),
        "count": len(records),
        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,
        "speed_min": min(speeds) if speeds else None,
        "speed_max": max(speeds) if speeds else None,
    }


class AdbInput(NodeInput):
    start_time: RequiredTime
    end_time: RequiredTime
    frequency_hz: float = Field(default=20.0, gt=0, le=100)
    timing_jitter_ms: int = Field(default=2, ge=0, le=100)
    num_targets: int = Field(default=3, ge=0, le=20)
    ego_speed_kmh: float = Field(default=60.0, ge=0, le=200)
    output_path: str = "input/adb_targets.jsonl"
    random_seed: int | None = None


@node(
    "repro.datagen.adb",
    inputs=AdbInput,
    tags=["repro", "generation"],
    description="Generate ADB target detections as JSONL.",
)
def generate_adb_node(ctx: NodeContext, inputs: AdbInput) -> dict[str, Any]:
    start_ms, end_ms = _time_bounds(inputs.start_time, inputs.end_time)
    records = generate_adb_targets(
        start_time=start_ms,
        end_time=end_ms,
        frequency_hz=inputs.frequency_hz,
        num_targets=inputs.num_targets,
        ego_speed_kmh=inputs.ego_speed_kmh,
        timing_jitter_ms=inputs.timing_jitter_ms,
        random_seed=inputs.random_seed,
    )
    output_path = save_jsonl(records, ctx.path(inputs.output_path))
    total_targets = sum(len(record["targets"]) for record in records)
    return {
        "output_path": str(output_path),
        "count": len(records),
        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,
        "average_targets": (total_targets / len(records)) if records else 0.0,
    }
