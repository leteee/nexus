"""
Nexus plugin adapters for repro (data replay) module.

Adapts video replay and data rendering logic to Nexus plugin interface.
"""

import logging
from typing import Any, Union, Optional
from pathlib import Path

from pydantic import Field

from nexus.core.context import PluginContext
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

from nexus.contrib.repro.video import extract_frames, compose_video, render_all_frames
from nexus.contrib.repro.common.io import save_jsonl
from nexus.contrib.repro.common.utils import (
    parse_time_string,
    parse_time_value,
    get_video_metadata,
)
from nexus.contrib.repro.datagen import (
    generate_timeline_with_jitter,
    generate_speed_data_event_driven,
    generate_adb_target_data,
    save_timeline_csv,
    SpeedProfile,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def resolve_video_path_with_glob(ctx: PluginContext, video_path_pattern: str) -> Path:
    """
    Resolve video path with glob pattern support.

    Supports wildcards like *, ?, [, ] for pattern matching.
    Returns the first matching file sorted alphabetically.

    Args:
        ctx: Plugin context for path resolution and logging
        video_path_pattern: Path pattern (can contain wildcards)

    Returns:
        Resolved absolute path to the first matching video file

    Raises:
        FileNotFoundError: If no files match the pattern

    Examples:
        - "input/driving.mp4" -> Direct file path
        - "input/*.mp4" -> First .mp4 file in input/
        - "input/video_*.mp4" -> First file matching pattern
    """
    # Resolve the path pattern first
    resolved_pattern = ctx.resolve_path(video_path_pattern)

    # Check if pattern contains wildcards
    if any(char in str(resolved_pattern) for char in ['*', '?', '[', ']']):
        # Use glob to find matching files
        parent_dir = resolved_pattern.parent if resolved_pattern.parent.exists() else Path.cwd()
        pattern = resolved_pattern.name

        matching_files = sorted(parent_dir.glob(pattern))

        if not matching_files:
            raise FileNotFoundError(
                f"No video files found matching pattern: {video_path_pattern} "
                f"(resolved to: {resolved_pattern})"
            )

        video_path = matching_files[0]
        logger.info(
            f"Matched {len(matching_files)} file(s) with pattern '{video_path_pattern}', "
            f"using first: {video_path.name}"
        )
        return video_path
    else:
        return resolved_pattern


# =============================================================================
# Video Processing Plugins
# =============================================================================


class VideoSplitterConfig(PluginConfig):
    """Configuration for video frame extraction."""

    video_path: str = Field(
        description="Path to input video file (MP4, AVI, MOV supported)"
    )
    output_path: str = Field(
        default="frames",
        description="Output directory for extracted frame images"
    )
    frame_pattern: str = Field(
        default="frame_{:06d}.png",
        description="Frame filename pattern with zero-padded numbering (Python format string)"
    )


class VideoComposerConfig(PluginConfig):
    """Configuration for composing video from frame images."""

    frames_dir: str = Field(
        default="frames",
        description="Directory containing input frame images"
    )
    output_path: str = Field(
        default="output.mp4",
        description="Output video file path"
    )
    fps: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Video frame rate in frames per second"
    )
    frame_pattern: str = Field(
        default="frame_{:06d}.png",
        description="Frame filename pattern to match input files"
    )
    codec: str = Field(
        default="mp4v",
        description="Video codec for encoding (mp4v, avc1, etc.)"
    )
    # Time range support (alternative to frame index)
    start_time: Union[str, float, None] = Field(
        default=None,
        description="Start time for video clip (None=beginning, timestamp_ms as float, or time string like '2025-10-27 12:00:00')"
    )
    end_time: Union[str, float, None] = Field(
        default=None,
        description="End time for video clip (None=end, timestamp_ms as float, or time string)"
    )
    timestamps_path: Optional[str] = Field(
        default=None,
        description="Path to frame timestamps CSV (None to use frames_dir/frame_timestamps.csv)"
    )
    # Frame index range support (alternative to time range)
    start_frame: int = Field(
        default=0,
        ge=0,
        description="First frame index to include (0-based, used if start_time is None)"
    )
    end_frame: Optional[int] = Field(
        default=None,
        description="Last frame index to include (None for all frames, used if end_time is None)"
    )


@plugin(name="Video Splitter", config=VideoSplitterConfig)
def split_video_to_frames(ctx: PluginContext) -> Any:
    """
    Extract all frames from video and save as images.

    Creates individual frame images in PNG format.
    Output stored in shared context for downstream plugins.

    Note: Use a separate Timeline Generator plugin to create
    frame_timestamps.csv with real acquisition times.

    video_path supports glob patterns:
        - "input/driving.mp4" -> Direct file path
        - "input/*.mp4" -> First .mp4 file in input/
        - "input/video_*.mp4" -> First file matching pattern
    """
    config: VideoSplitterConfig = ctx.config  # type: ignore

    # Resolve video path with glob pattern support
    video_path = resolve_video_path_with_glob(ctx, config.video_path)
    output_path = ctx.resolve_path(config.output_path)

    logger.info(f"Extracting frames from {video_path}")

    metadata = extract_frames(
        video_path,
        output_path,
        frame_pattern=config.frame_pattern,
    )

    logger.info(
        f"Extracted {metadata.total_frames} frames at {metadata.fps:.2f} FPS"
    )

    # Store metadata for downstream plugins
    ctx.remember("video_metadata", metadata)
    ctx.remember("frames_dir", output_path)

    return metadata


@plugin(name="Video Composer", config=VideoComposerConfig)
def compose_frames_to_video(ctx: PluginContext) -> Any:
    """
    Compose video from extracted frame images.

    Can use frames from Video Splitter or custom rendered frames.
    Supports both time range and frame index range selection for creating clips.

    Time range (preferred):
        start_time: "2025-10-27 08:30:15" or timestamp_ms
        end_time: "2025-10-27 08:30:25" or timestamp_ms
        timestamps_path: Path to frame_timestamps.csv (auto-detected if None)

    Frame index range (alternative):
        start_frame: 150
        end_frame: 450

    Priority: If start_time/end_time are provided, they override start_frame/end_frame.
    """
    import pandas as pd

    config: VideoComposerConfig = ctx.config  # type: ignore
    frames_dir = ctx.resolve_path(config.frames_dir)
    output_path = ctx.resolve_path(config.output_path)

    # Determine frame range
    start_frame_idx = config.start_frame
    end_frame_idx = config.end_frame

    # If time range is specified, convert to frame indices
    if config.start_time is not None or config.end_time is not None:
        # Load timestamps
        if config.timestamps_path:
            timestamps_path = ctx.resolve_path(config.timestamps_path)
        else:
            timestamps_path = frames_dir / "frame_timestamps.csv"

        if not timestamps_path.exists():
            raise FileNotFoundError(
                f"Timestamps file not found: {timestamps_path}. "
                f"Required when using start_time/end_time."
            )

        logger.info(f"Loading frame timestamps from {timestamps_path}")
        frame_times = pd.read_csv(timestamps_path)

        # Parse time values
        start_time_ms = parse_time_value(config.start_time)
        end_time_ms = parse_time_value(config.end_time)

        # Convert time range to frame indices
        if start_time_ms is not None:
            # Find first frame >= start_time
            matching_frames = frame_times[frame_times["timestamp_ms"] >= start_time_ms]
            if len(matching_frames) > 0:
                start_frame_idx = int(matching_frames.iloc[0]["frame_index"])
                logger.info(
                    f"Start time {start_time_ms} ms -> frame {start_frame_idx}"
                )
            else:
                logger.warning(
                    f"No frames found after start_time {start_time_ms} ms, "
                    f"using start_frame={start_frame_idx}"
                )

        if end_time_ms is not None:
            # Find last frame <= end_time
            matching_frames = frame_times[frame_times["timestamp_ms"] <= end_time_ms]
            if len(matching_frames) > 0:
                end_frame_idx = int(matching_frames.iloc[-1]["frame_index"])
                logger.info(
                    f"End time {end_time_ms} ms -> frame {end_frame_idx}"
                )
            else:
                logger.warning(
                    f"No frames found before end_time {end_time_ms} ms, "
                    f"using end_frame={end_frame_idx}"
                )

    logger.info(
        f"Composing video from {frames_dir} "
        f"(frame range: {start_frame_idx} to {end_frame_idx or 'end'})"
    )

    result_path = compose_video(
        frames_dir,
        output_path,
        fps=config.fps,
        frame_pattern=config.frame_pattern,
        codec=config.codec,
        start_frame=start_frame_idx,
        end_frame=end_frame_idx,
    )

    logger.info(f"Created video: {result_path}")

    ctx.remember("output_video", result_path)

    return result_path


# =============================================================================
# Data Rendering Plugin
# =============================================================================


class DataRendererConfig(PluginConfig):
    """Configuration for rendering data overlays on video frames."""

    start_time: Union[str, float, None] = Field(
        default=None,
        description="Start time for rendering (None=beginning, timestamp_ms as float, or time string like '2025-10-27 12:00:00')"
    )
    end_time: Union[str, float, None] = Field(
        default=None,
        description="End time for rendering (None=end, timestamp_ms as float, or time string)"
    )
    frames_dir: str = Field(
        default="frames",
        description="Directory containing extracted video frames"
    )
    output_path: str = Field(
        default="rendered_frames",
        description="Output directory for frames with rendered data overlays"
    )
    frame_pattern: str = Field(
        default="frame_{:06d}.png",
        description="Frame filename pattern to match input files"
    )
    timestamps_path: Optional[str] = Field(
        default=None,
        description="Path to custom frame timestamps CSV (None to use frames_dir/frame_timestamps.csv)"
    )
    sensors: list[dict] = Field(
        default=[],
        description="List of sensor configurations, each with a 'name', 'path', and optional 'time_offset_ms'."
    )
    renderers: list[dict] = Field(
        description="List of renderer configurations with 'class' (full qualified class name) and 'kwargs'"
    )


@plugin(name="Data Renderer", config=DataRendererConfig)
def render_data_on_frames(ctx: PluginContext) -> Any:
    """
    Apply multiple data renderers to all video frames.

    Uses dynamic class import to load renderer classes by full qualified name.
    Renderers are automatically instantiated and reused for all frames.

    Path Resolution Convention:
        All parameters ending with '_path' in renderer kwargs are automatically
        resolved to absolute paths relative to the case directory.

        Example:
            data_path: "input/speed.jsonl"  -> /abs/case/path/input/speed.jsonl
            calibration_path: "calib.yaml"  -> /abs/case/path/calib.yaml

        To disable auto-resolution for a specific field, use:
            Field(..., json_schema_extra={"skip_path_resolve": True})

    Config format (use full class names):
        renderers:
          - class: "nexus.contrib.repro.renderers.SpeedRenderer"
            enable: true  # Optional, default is true
            kwargs:
              data_path: "input/speed.jsonl"       # Auto-resolved
              position: [30, 60]
              tolerance_ms: 5000

          - class: "nexus.contrib.repro.renderers.TargetRenderer"
            enable: false  # Set to false to skip this renderer
            kwargs:
              data_path: "input/adb_targets.jsonl"      # Auto-resolved
              calibration_path: "camera_calibration.yaml"  # Auto-resolved
              tolerance_ms: 50

    Renderer enable field:
        - enable: true (default, executes the renderer)
        - enable: false (skips the renderer)
        When disabled, log shows: "Skipping disabled renderer (#N): ClassName"

    Config:
        frames_dir: Directory containing extracted frames
        output_path: Directory for rendered frames
        frame_pattern: Frame filename pattern
        timestamps_path: Optional custom timestamps CSV path
        renderers: List of renderer configurations (use "class" for full qualified class names)

    Note:
        To show frame info, add FrameInfoRenderer to the renderers list:
        {
            "class": "nexus.contrib.repro.renderers.FrameInfoRenderer",
            "kwargs": {
                "position": [10, 30],
                "format": "datetime"
            }
        }
    """
    config: DataRendererConfig = ctx.config  # type: ignore

    # Resolve top-level paths
    frames_dir = ctx.resolve_path(config.frames_dir)
    output_path = ctx.resolve_path(config.output_path)

    if config.timestamps_path:
        timestamps_path = ctx.resolve_path(config.timestamps_path)
    else:
        timestamps_path = frames_dir / "frame_timestamps.csv"

    # Resolve paths in renderer kwargs automatically using '*_path' convention
    renderer_configs = []
    for idx, renderer_config in enumerate(config.renderers, start=1):
        # Check if renderer is enabled (default: true)
        if not renderer_config.get("enable", True):
            renderer_class = renderer_config.get("class", "unknown")
            logger.info(f"Skipping disabled renderer (#{idx}): {renderer_class}")
            continue

        rc = renderer_config.copy()
        kwargs = rc.get("kwargs", {})

        # Automatically resolve all *_path parameters
        resolved_kwargs = ctx.auto_resolve_paths(kwargs)

        rc["kwargs"] = resolved_kwargs
        renderer_configs.append(rc)

    # Call repro module function
    logger.info(f"Rendering frames from {frames_dir}")

    # Parse time range
    start_time_ms = parse_time_value(config.start_time)
    end_time_ms = parse_time_value(config.end_time)

    if start_time_ms is not None:
        logger.info(f"Start time: {start_time_ms} ms")
    if end_time_ms is not None:
        logger.info(f"End time: {end_time_ms} ms")

    # Resolve paths and parameters for the 'sensors' block
    resolved_sensor_configs = []
    for sensor_conf in config.sensors:
        resolved_conf = dict(sensor_conf)
        if 'path' in resolved_conf:
            resolved_conf['path'] = ctx.resolve_path(resolved_conf['path'])
        resolved_sensor_configs.append(resolved_conf)

    def progress_callback(count: int, total: int) -> None:
        """Progress callback for logging."""
        if count % 100 == 0:
            logger.info(f"Rendered {count}/{total} frames...")

    output_path = render_all_frames(
        frames_dir=frames_dir,
        output_path=output_path,
        timestamps_path=timestamps_path,
        sensor_configs=resolved_sensor_configs,
        renderer_configs=renderer_configs,
        frame_pattern=config.frame_pattern,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        progress_callback=progress_callback,
        ctx=ctx,  # Pass context to renderers
    )

    logger.info(f"Completed: rendered frames to {output_path}")

    # Store output dir for Video Composer
    ctx.remember("rendered_frames_dir", output_path)

    return output_path


# =============================================================================
# Data Generation Plugins
# =============================================================================


class TimelineGeneratorConfig(PluginConfig):
    """Configuration for generating frame timeline with realistic timestamp jitter."""

    video_path: Optional[str] = Field(
        default=None,
        description="Video file path to auto-extract FPS and duration (alternative to manual fps/total_frames)"
    )
    fps: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=120.0,
        description="Video frame rate in FPS (required if video_path not provided)"
    )
    total_frames: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of frames to generate (required if video_path not provided)"
    )
    start_time: str = Field(
        default="2025-10-27 00:00:00",
        description="Starting timestamp in 'YYYY-MM-DD HH:MM:SS' format"
    )
    jitter_ms: int = Field(
        default=2,
        ge=0,
        le=100,
        description="Maximum random timing jitter in milliseconds (±jitter_ms)"
    )
    output_csv: str = Field(
        default="output/timeline.csv",
        description="Output CSV file path for frame timestamps"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible jitter generation"
    )


@plugin(name="Timeline Generator", config=TimelineGeneratorConfig)
def generate_timeline(ctx: PluginContext) -> Any:
    """
    Generate frame timeline with realistic timestamp jitter.

    Simulates real-world data collection where timestamps are never perfectly stable.
    Adds random jitter (±1.5ms by default) to each frame timestamp.

    Can auto-extract FPS and duration from video, or use manual configuration.

    video_path supports glob patterns:
        - "input/driving.mp4" -> Direct file path
        - "input/*.mp4" -> First .mp4 file in input/
        - "input/video_*.mp4" -> First file matching pattern

    Config:
        video_path: (Optional) Video file to extract FPS and duration from (supports glob patterns)
        fps: Video frame rate (required if video_path not provided)
        total_frames: Number of frames to generate (required if video_path not provided)
        start_time: Starting time in format "YYYY-MM-DD HH:MM:SS"
        jitter_ms: Maximum jitter to add (±jitter_ms)
        output_csv: Output CSV file path
        random_seed: Random seed for reproducibility

    Output CSV format:
        frame_index,timestamp_ms
        0,1759284000000.0
        1,1759284000034.8
        ...
    """
    config: TimelineGeneratorConfig = ctx.config  # type: ignore
    # Parse start time to timestamp
    start_timestamp_ms = parse_time_string(config.start_time)
    logger.info(f"Start time: {config.start_time} -> {start_timestamp_ms} ms")

    # Get FPS and total_frames from video or config
    if config.video_path:
        video_path = resolve_video_path_with_glob(ctx, config.video_path)
        logger.info(f"Extracting metadata from video: {video_path}")

        video_meta = get_video_metadata(video_path)
        fps = video_meta["fps"]
        total_frames = video_meta["total_frames"]

        logger.info(
            f"Video: {total_frames} frames at {fps:.2f} FPS "
            f"(duration: {video_meta['duration_s']:.2f}s)"
        )
    else:
        if config.fps is None or config.total_frames is None:
            raise ValueError(
                "Either video_path or both fps and total_frames must be provided"
            )
        fps = config.fps
        total_frames = config.total_frames
        logger.info(f"Using manual config: {total_frames} frames at {fps} FPS")

    timeline = generate_timeline_with_jitter(
        fps=fps,
        total_frames=total_frames,
        start_timestamp_ms=start_timestamp_ms,
        jitter_ms=config.jitter_ms,
        random_seed=config.random_seed,
    )

    output_path = ctx.resolve_path(config.output_csv)
    save_timeline_csv(timeline, output_path)

    logger.info(f"Timeline saved to {output_path}")
    logger.info(
        f"Time range: {timeline[0]['timestamp_ms']:.1f} - {timeline[-1]['timestamp_ms']:.1f} ms"
    )

    # Store in context for other plugins
    ctx.remember("timeline_path", output_path)
    ctx.remember("start_timestamp_ms", start_timestamp_ms)
    ctx.remember("video_duration_s", (total_frames / fps) if fps > 0 else 0)

    return output_path


class SpeedDataGeneratorConfig(PluginConfig):
    """Configuration for generating event-driven speed data."""

    start_time: Optional[str] = Field(
        default=None,
        description="Starting timestamp in 'YYYY-MM-DD HH:MM:SS' format (None to use Timeline Generator context)"
    )
    video_path: Optional[str] = Field(
        default=None,
        description="Video file path to auto-extract duration (alternative to manual duration_s)"
    )
    duration_s: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Data generation duration in seconds (required if video_path not provided)"
    )
    max_interval_s: float = Field(
        default=5.0,
        ge=0.1,
        le=60.0,
        description="Maximum interval without sending data in seconds"
    )
    speed_change_threshold: float = Field(
        default=2.0,
        ge=0.0,
        description="Minimum speed change in km/h to trigger event"
    )
    output_jsonl: str = Field(
        default="output/speed.jsonl",
        description="Output JSONL file path for speed data"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible data generation"
    )
    use_default_profile: bool = Field(
        default=True,
        description="Use default realistic driving speed profile"
    )
    custom_profiles: Optional[list] = Field(
        default=None,
        description="Custom speed profiles (list of speed segments, used if use_default_profile=False)"
    )


@plugin(name="Speed Data Generator", config=SpeedDataGeneratorConfig)
def generate_speed_data(ctx: PluginContext) -> Any:
    """
    Generate event-driven speed data.

    Speed is recorded only when:
    1. Speed changes by more than threshold (default 2 km/h)
    2. At least max_interval_s has elapsed (default 5s)

    Mimics real sensor behavior: event-driven with periodic updates.
    Data generation is INDEPENDENT of video duration.

    video_path supports glob patterns:
        - "input/driving.mp4" -> Direct file path
        - "input/*.mp4" -> First .mp4 file in input/
        - "input/video_*.mp4" -> First file matching pattern

    Config:
        start_time: Starting time string (e.g., "2025-10-27 00:00:00")
                    If not provided, uses context from Timeline Generator
        video_path: (Optional) Video to extract duration from (supports glob patterns)
        duration_s: Data generation duration (required if video_path not provided)
        max_interval_s: Maximum interval without sending data (default 5s)
        speed_change_threshold: Minimum speed change to trigger event (km/h)
        output_jsonl: Output JSONL file path
        random_seed: Random seed for reproducibility
        use_default_profile: Use default realistic driving profile
        custom_profiles: Custom speed profiles (if use_default_profile=False)

    Output JSONL format:
        {"timestamp_ms": 1759284000000.0, "speed": 0.0}
        {"timestamp_ms": 1759284002150.5, "speed": 12.3}
        ...
    """
    config: SpeedDataGeneratorConfig = ctx.config  # type: ignore
    # Get start timestamp from config or context
    if config.start_time:
        start_timestamp_ms = parse_time_string(config.start_time)
        logger.info(f"Start time: {config.start_time} -> {start_timestamp_ms} ms")
    elif hasattr(ctx, 'recall') and ctx.recall("start_timestamp_ms"):
        start_timestamp_ms = ctx.recall("start_timestamp_ms")
        logger.info(f"Using start_timestamp_ms from context: {start_timestamp_ms}")
    else:
        raise ValueError("start_time must be provided or Timeline Generator must run first")

    # Get duration from video or config or context
    if config.video_path:
        video_path = resolve_video_path_with_glob(ctx, config.video_path)
        video_meta = get_video_metadata(video_path)
        duration_s = video_meta["duration_s"]
        logger.info(f"Using video duration: {duration_s:.2f}s from {video_path}")
    elif config.duration_s is not None:
        duration_s = config.duration_s
        logger.info(f"Using configured duration: {duration_s}s")
    elif hasattr(ctx, 'recall') and ctx.recall("video_duration_s"):
        duration_s = ctx.recall("video_duration_s")
        logger.info(f"Using duration from context: {duration_s:.2f}s")
    else:
        raise ValueError("duration_s or video_path must be provided")

    logger.info(
        f"Generating speed data: {duration_s}s, "
        f"event threshold: {config.speed_change_threshold} km/h, "
        f"max interval: {config.max_interval_s}s"
    )

    speed_data = generate_speed_data_event_driven(
        start_timestamp_ms=start_timestamp_ms,
        duration_s=duration_s,
        speed_profiles=None if config.use_default_profile else config.custom_profiles,
        max_interval_s=config.max_interval_s,
        speed_change_threshold=config.speed_change_threshold,
        random_seed=config.random_seed,
    )

    output_path = ctx.resolve_path(config.output_jsonl)
    save_jsonl(speed_data, output_path)

    logger.info(f"Generated {len(speed_data)} speed events")
    logger.info(f"Speed data saved to {output_path}")

    if speed_data:
        speeds = [d["speed"] for d in speed_data]
        logger.info(f"Speed range: {min(speeds):.1f} - {max(speeds):.1f} km/h")

    return output_path


class ADBTargetGeneratorConfig(PluginConfig):
    """Configuration for generating ADB (Adaptive Driving Beam) target detection data."""

    start_time: Optional[str] = Field(
        default=None,
        description="Starting timestamp in 'YYYY-MM-DD HH:MM:SS' format (None to use Timeline Generator context)"
    )
    video_path: Optional[str] = Field(
        default=None,
        description="Video file path to auto-extract duration (alternative to manual duration_s)"
    )
    duration_s: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Data generation duration in seconds (required if video_path not provided)"
    )
    frequency_hz: float = Field(
        default=20.0,
        ge=1.0,
        le=100.0,
        description="Target data generation frequency in Hz"
    )
    timing_jitter_ms: int = Field(
        default=2,
        ge=0,
        le=100,
        description="Random timing jitter in milliseconds for realistic reception timing (±jitter_ms)"
    )
    num_targets: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Number of concurrent targets in the scene"
    )
    ego_speed_kmh: float = Field(
        default=60.0,
        ge=0.0,
        le=200.0,
        description="Ego vehicle speed in km/h"
    )
    output_jsonl: str = Field(
        default="output/targets.jsonl",
        description="Output JSONL file path for target data"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible data generation"
    )


@plugin(name="ADB Target Generator", config=ADBTargetGeneratorConfig)
def generate_adb_targets(ctx: PluginContext) -> Any:
    """
    Generate ADB (Adaptive Driving Beam) target detection data.

    Simulates targets (vehicles, pedestrians, etc.) detected in the vehicle's
    forward field of view for adaptive headlight systems.
    Data is generated at 20Hz with realistic timing jitter.
    Data generation is INDEPENDENT of video duration.

    FOV: 16° horizontal × 9° vertical
    Detection range: 5m to 150m
    Frequency: 20Hz with timing jitter (±2ms default)

    video_path supports glob patterns:
        - "input/driving.mp4" -> Direct file path
        - "input/*.mp4" -> First .mp4 file in input/
        - "input/video_*.mp4" -> First file matching pattern

    Config:
        start_time: Starting time string (e.g., "2025-10-27 00:00:00")
                    If not provided, uses context from Timeline Generator
        video_path: (Optional) Video to extract duration from (supports glob patterns)
        duration_s: Data generation duration (required if video_path not provided)
        frequency_hz: Target data frequency (default 20Hz)
        timing_jitter_ms: Random timing error in reception (±ms)
        num_targets: Number of concurrent targets (2-3 typical)
        ego_speed_kmh: Speed of ego vehicle (km/h)
        output_jsonl: Output JSONL file path
        random_seed: Random seed for reproducibility

    Output JSONL format:
        {
          "timestamp_ms": 1759284000000.0,
          "targets": [
            {
              "id": 1,
              "type": "car",
              "distance_m": 45.2,
              "angle_left": 1.8,
              "angle_right": 2.8,
              "angle_top": -0.3,
              "angle_bottom": -0.7
            },
            ...
          ]
        }
    """
    config: ADBTargetGeneratorConfig = ctx.config  # type: ignore
    # Get start timestamp from config or context
    if config.start_time:
        start_timestamp_ms = parse_time_string(config.start_time)
        logger.info(f"Start time: {config.start_time} -> {start_timestamp_ms} ms")
    elif hasattr(ctx, 'recall') and ctx.recall("start_timestamp_ms"):
        start_timestamp_ms = ctx.recall("start_timestamp_ms")
        logger.info(f"Using start_timestamp_ms from context: {start_timestamp_ms}")
    else:
        raise ValueError("start_time must be provided or Timeline Generator must run first")

    # Get duration from video or config or context
    if config.video_path:
        video_path = resolve_video_path_with_glob(ctx, config.video_path)
        video_meta = get_video_metadata(video_path)
        duration_s = video_meta["duration_s"]
        logger.info(f"Using video duration: {duration_s:.2f}s from {video_path}")
    elif config.duration_s is not None:
        duration_s = config.duration_s
        logger.info(f"Using configured duration: {duration_s}s")
    elif hasattr(ctx, 'recall') and ctx.recall("video_duration_s"):
        duration_s = ctx.recall("video_duration_s")
        logger.info(f"Using duration from context: {duration_s:.2f}s")
    else:
        raise ValueError("duration_s or video_path must be provided")

    logger.info(
        f"Generating ADB target data: {duration_s}s at {config.frequency_hz}Hz, "
        f"{config.num_targets} targets, timing jitter: ±{config.timing_jitter_ms}ms"
    )

    target_data = generate_adb_target_data(
        start_timestamp_ms=start_timestamp_ms,
        duration_s=duration_s,
        frequency_hz=config.frequency_hz,
        num_targets=config.num_targets,
        ego_speed_kmh=config.ego_speed_kmh,
        timing_jitter_ms=config.timing_jitter_ms,
        random_seed=config.random_seed,
    )

    output_path = ctx.resolve_path(config.output_jsonl)
    save_jsonl(target_data, output_path)

    logger.info(f"Generated {len(target_data)} target frames")
    logger.info(f"Target data saved to {output_path}")

    # Statistics
    total_targets = sum(len(d["targets"]) for d in target_data)
    avg_targets = total_targets / len(target_data) if target_data else 0
    logger.info(f"Average targets per frame: {avg_targets:.1f}")


# =============================================================================
# Synthetic Video Generation Plugin
# =============================================================================


class SyntheticVideoGeneratorConfig(PluginConfig):
    """Configuration for generating synthetic driving video."""

    output_path: str = Field(
        default="input/synthetic_driving.mp4",
        description="Output video file path"
    )
    duration_s: float = Field(
        default=60.0,
        ge=1.0,
        le=3600.0,
        description="Video duration in seconds"
    )
    fps: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Video frame rate in frames per second"
    )
    width: int = Field(
        default=1920,
        ge=320,
        le=7680,
        description="Video width in pixels"
    )
    height: int = Field(
        default=1080,
        ge=240,
        le=4320,
        description="Video height in pixels"
    )
    speed_kmh: float = Field(
        default=60.0,
        ge=0.0,
        le=200.0,
        description="Simulated vehicle speed in km/h"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible video generation"
    )


@plugin(name="Synthetic Video Generator", config=SyntheticVideoGeneratorConfig)
def generate_synthetic_video(ctx: PluginContext) -> Any:
    """
    Generate synthetic video simulating forward driving view.

    Creates a video with road lane markings and perspective projection
    to simulate vehicle motion. Useful for testing without real video data.

    Config:
        output_path: Output video file path (default: "input/synthetic_driving.mp4")
        duration_s: Video duration in seconds (default: 60.0)
        fps: Frames per second (default: 30.0)
        width: Video width in pixels (default: 1920)
        height: Video height in pixels (default: 1080)
        speed_kmh: Simulated vehicle speed (default: 60.0)
        random_seed: Random seed for reproducibility (optional)

    Generates:
        - Video file with simulated forward driving view
        - Road lane markings (dashed center line, solid edges)
        - Perspective projection simulating camera view
        - Moving pattern simulating vehicle motion

    Context data saved:
        - video_fps: Video FPS
        - video_total_frames: Total number of frames
        - video_duration_s: Video duration in seconds

    Example:
        pipeline:
          - plugin: "Synthetic Video Generator"
            config:
              output_path: "input/synthetic_driving.mp4"
              duration_s: 60.0
              fps: 30.0
              width: 1920
              height: 1080
              speed_kmh: 60.0
              random_seed: 42
    """
    from nexus.contrib.repro.datagen import generate_driving_video

    config: SyntheticVideoGeneratorConfig = ctx.config  # type: ignore
    output_path = ctx.resolve_path(config.output_path)

    logger.info(
        f"Generating synthetic video: {config.duration_s}s at {config.fps} FPS, "
        f"{config.width}x{config.height}, speed: {config.speed_kmh} km/h"
    )

    metadata = generate_driving_video(
        output_path=output_path,
        duration_s=config.duration_s,
        fps=config.fps,
        width=config.width,
        height=config.height,
        speed_kmh=config.speed_kmh,
        random_seed=config.random_seed,
    )

    logger.info(f"Video saved to {output_path}")
    logger.info(
        f"Generated {metadata['total_frames']} frames "
        f"({metadata['duration_s']}s at {metadata['fps']} FPS)"
    )

    # Save video metadata to context for downstream plugins
    ctx.remember("video_fps", metadata["fps"])
    ctx.remember("video_total_frames", metadata["total_frames"])
    ctx.remember("video_duration_s", metadata["duration_s"])

    return metadata


# =============================================================================
# Timeline and Frame Generation Plugins
# =============================================================================


class SimpleTimelineGeneratorConfig(PluginConfig):
    """Configuration for generating a simple timeline based on duration."""

    start_time: str = Field(
        default="2025-10-27 00:00:00",
        description="Starting timestamp in 'YYYY-MM-DD HH:MM:SS' format"
    )
    end_time: str = Field(
        description="Ending timestamp in 'YYYY-MM-DD HH:MM:SS' format"
    )
    fps: float = Field(
        default=30.0,
        ge=1.0,
        description="Frames per second for the timeline"
    )
    timestamps_path: str = Field(
        default="output/timeline.csv",
        description="Output CSV file path for frame timestamps"
    )
    jitter_ms: int = Field(
        default=0,
        ge=0,
        description="Maximum random timing jitter in milliseconds (±jitter_ms). Default is 0 for no jitter."
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible jitter generation"
    )

@plugin(name="Simple Timeline Generator", config=SimpleTimelineGeneratorConfig)
def generate_simple_timeline(ctx: PluginContext) -> Any:
    """
    Generate a frame timeline based on a start time, end time, and FPS.

    This plugin is useful for creating a time foundation for data replay
    when no real video is available.
    """
    config: SimpleTimelineGeneratorConfig = ctx.config  # type: ignore

    start_timestamp_ms = parse_time_string(config.start_time)
    end_timestamp_ms = parse_time_string(config.end_time)

    if start_timestamp_ms >= end_timestamp_ms:
        raise ValueError("start_time must be before end_time")

    duration_s = (end_timestamp_ms - start_timestamp_ms) / 1000.0
    total_frames = int(duration_s * config.fps)

    logger.info(
        f"Generating timeline: {duration_s:.2f}s at {config.fps} FPS -> {total_frames} frames"
    )

    timeline = generate_timeline_with_jitter(
        fps=config.fps,
        total_frames=total_frames,
        start_timestamp_ms=start_timestamp_ms,
        jitter_ms=config.jitter_ms,
        random_seed=config.random_seed,
    )

    output_path = ctx.resolve_path(config.timestamps_path)
    save_timeline_csv(timeline, output_path)

    logger.info(f"Timeline saved to {output_path}")

    return output_path


class BlankFrameGeneratorConfig(PluginConfig):
    """Configuration for generating blank video frames from a timeline."""

    timestamps_path: str = Field(
        description="Path to timeline CSV file."
    )
    output_path: str = Field(
        default="frames",
        description="Output directory for generated blank frames"
    )
    width: int = Field(
        default=1920,
        description="Width of the blank frames in pixels"
    )
    height: int = Field(
        default=1080,
        description="Height of the blank frames in pixels"
    )
    frame_pattern: str = Field(
        default="frame_{:06d}.png",
        description="Filename pattern for the output frames."
    )
    color: tuple[int, int, int] = Field(
        default=(0, 0, 0),
        description="Color of the blank frames in BGR format (e.g., (0, 0, 0) for black)."
    )

@plugin(name="Blank Frame Generator", config=BlankFrameGeneratorConfig)
def generate_blank_frames(ctx: PluginContext) -> Any:
    """
    Generate blank video frames based on a timeline file.

    This plugin reads a timeline CSV and creates a blank image for each
    frame entry, which is useful for replaying data without a real video source.
    """
    import pandas as pd
    import numpy as np
    import cv2
    from tqdm import tqdm

    config: BlankFrameGeneratorConfig = ctx.config  # type: ignore

    timestamps_path = ctx.resolve_path(config.timestamps_path)
    if not timestamps_path.exists():
        raise FileNotFoundError(f"Timeline file not found: {timestamps_path}")

    output_path = ctx.resolve_path(config.output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Reading timeline from {timestamps_path}")
    timeline_df = pd.read_csv(timestamps_path)
    total_frames = len(timeline_df)

    logger.info(
        f"Generating {total_frames} blank frames ({config.width}x{config.height}) "
        f"into {output_path}"
    )

    # Create a blank image template
    blank_image = np.full((config.height, config.width, 3), config.color, dtype=np.uint8)

    with tqdm(total=total_frames, desc="Generating blank frames", unit="frame") as pbar:
        for _, row in timeline_df.iterrows():
            frame_idx = int(row["frame_index"])
            frame_file = output_path / config.frame_pattern.format(frame_idx)
            cv2.imwrite(str(frame_file), blank_image)
            pbar.update(1)

    logger.info("Blank frame generation complete.")

    return output_path

