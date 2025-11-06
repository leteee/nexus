"""
Nexus plugin adapters for repro (data replay) module.

Adapts video replay and data rendering logic to Nexus plugin interface.
"""

from typing import Any, Union, Optional

from nexus.core.context import PluginContext
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

from nexus.contrib.repro.video import extract_frames, compose_video, render_all_frames
from nexus.contrib.repro.io import save_jsonl
from nexus.contrib.repro.utils import (
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


# =============================================================================
# Video Processing Plugins
# =============================================================================


class VideoSplitterConfig(PluginConfig):
    video_path: str
    output_dir: str = "frames"
    frame_pattern: str = "frame_{:06d}.png"


class VideoComposerConfig(PluginConfig):
    frames_dir: str = "frames"
    output_path: str = "output.mp4"
    fps: float = 30.0
    frame_pattern: str = "frame_{:06d}.png"
    codec: str = "mp4v"
    start_frame: int = 0
    end_frame: Optional[int] = None


@plugin(name="Video Splitter", config=VideoSplitterConfig)
def split_video_to_frames(ctx: PluginContext) -> Any:
    """
    Extract all frames from video and save as images.

    Creates individual frame images in PNG format.
    Output stored in shared context for downstream plugins.

    Note: Use a separate Timeline Generator plugin to create
    frame_timestamps.csv with real acquisition times.
    """
    config: VideoSplitterConfig = ctx.config  # type: ignore
    video_path = ctx.resolve_path(config.video_path)
    output_dir = ctx.resolve_path(config.output_dir)

    ctx.logger.info(f"Extracting frames from {video_path}")

    metadata = extract_frames(
        video_path,
        output_dir,
        frame_pattern=config.frame_pattern,
    )

    ctx.logger.info(
        f"Extracted {metadata.total_frames} frames at {metadata.fps:.2f} FPS"
    )

    # Store metadata for downstream plugins
    ctx.remember("video_metadata", metadata)
    ctx.remember("frames_dir", output_dir)

    return metadata


@plugin(name="Video Composer", config=VideoComposerConfig)
def compose_frames_to_video(ctx: PluginContext) -> Any:
    """
    Compose video from sequence of frame images.

    Can use frames from Video Splitter or custom rendered frames.
    Supports frame range selection for creating clips.
    """
    config: VideoComposerConfig = ctx.config  # type: ignore
    frames_dir = ctx.resolve_path(config.frames_dir)
    output_path = ctx.resolve_path(config.output_path)

    ctx.logger.info(f"Composing video from {frames_dir}")

    result_path = compose_video(
        frames_dir,
        output_path,
        fps=config.fps,
        frame_pattern=config.frame_pattern,
        codec=config.codec,
        start_frame=config.start_frame,
        end_frame=config.end_frame,
    )

    ctx.logger.info(f"Created video: {result_path}")

    ctx.remember("output_video", result_path)

    return result_path


# =============================================================================
# Data Rendering Plugin
# =============================================================================


class DataRendererConfig(PluginConfig):
    # Time range control (video timeline is the primary timeline)
    start_time: Union[str, float, None] = None  # Start time: None, timestamp_ms, or time string
    end_time: Union[str, float, None] = None    # End time: None, timestamp_ms, or time string

    frames_dir: str = "frames"
    output_dir: str = "rendered_frames"
    frame_pattern: str = "frame_{:06d}.png"
    timestamps_path: Optional[str] = None  # Optional: custom timestamps CSV path
    show_frame_info: bool = True  # Show frame ID and timestamp overlay
    renderers: list[dict]  # List of {"class": "...", "kwargs": {...}}


@plugin(name="Data Renderer", config=DataRendererConfig)
def render_data_on_frames(ctx: PluginContext) -> Any:
    """
    Apply multiple data renderers to all video frames.

    This plugin adapts the repro.render_all_frames() function to Nexus.
    The actual rendering logic is implemented in the repro module.

    Config format:
        renderers:
          - class: "nexus.contrib.repro.renderers.SpeedRenderer"
            kwargs:
              data_path: "input/speed.jsonl"
              position: [30, 60]
              tolerance_ms: 5000

          - class: "nexus.contrib.repro.renderers.TargetRenderer"
            kwargs:
              data_path: "input/adb_targets.jsonl"
              calibration_path: "camera_calibration.yaml"
              tolerance_ms: 50

    Config:
        frames_dir: Directory containing extracted frames
        output_dir: Directory for rendered frames
        frame_pattern: Frame filename pattern
        timestamps_path: Optional custom timestamps CSV path
        show_frame_info: Show frame ID and timestamp overlay (default: True)
        renderers: List of renderer configurations
    """
    from pathlib import Path

    config: DataRendererConfig = ctx.config  # type: ignore
    # Resolve paths
    frames_dir = ctx.resolve_path(config.frames_dir)
    output_dir = ctx.resolve_path(config.output_dir)

    if config.timestamps_path:
        timestamps_path = ctx.resolve_path(config.timestamps_path)
    else:
        timestamps_path = frames_dir / "frame_timestamps.csv"

    # Resolve paths in renderer kwargs
    renderer_configs = []
    for renderer_config in config.renderers:
        rc = renderer_config.copy()
        kwargs = rc.get("kwargs", {}).copy()

        # Resolve file paths in kwargs
        for key in ["data_path", "calibration_path"]:
            if key in kwargs:
                kwargs[key] = ctx.resolve_path(kwargs[key])

        rc["kwargs"] = kwargs
        renderer_configs.append(rc)

    # Call repro module function
    ctx.logger.info(f"Rendering frames from {frames_dir}")

    # Parse time range
    start_time_ms = parse_time_value(config.start_time)
    end_time_ms = parse_time_value(config.end_time)

    if start_time_ms is not None:
        ctx.logger.info(f"Start time: {start_time_ms} ms")
    if end_time_ms is not None:
        ctx.logger.info(f"End time: {end_time_ms} ms")

    def progress_callback(count: int, total: int) -> None:
        """Progress callback for logging."""
        if count % 100 == 0:
            ctx.logger.info(f"Rendered {count}/{total} frames...")

    output_dir = render_all_frames(
        frames_dir=frames_dir,
        output_dir=output_dir,
        timestamps_path=timestamps_path,
        renderer_configs=renderer_configs,
        frame_pattern=config.frame_pattern,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        show_frame_info=config.show_frame_info,
        progress_callback=progress_callback,
    )

    ctx.logger.info(f"Completed: rendered frames to {output_dir}")

    # Store output dir for Video Composer
    ctx.remember("rendered_frames_dir", output_dir)

    return output_dir


# =============================================================================
# Data Generation Plugins
# =============================================================================


class TimelineGeneratorConfig(PluginConfig):
    video_path: Optional[str] = None  # Optional: auto-extract FPS and duration from video
    fps: Optional[float] = None  # Required if video_path not provided
    total_frames: Optional[int] = None  # Required if video_path not provided
    start_time: str = "2025-10-27 00:00:00"  # Time format (converted to timestamp)
    jitter_ms: int = 2  # Integer milliseconds for realistic jitter
    output_csv: str = "output/timeline.csv"
    random_seed: Optional[int] = None


@plugin(name="Timeline Generator", config=TimelineGeneratorConfig)
def generate_timeline(ctx: PluginContext) -> Any:
    """
    Generate frame timeline with realistic timestamp jitter.

    Simulates real-world data collection where timestamps are never perfectly stable.
    Adds random jitter (±1.5ms by default) to each frame timestamp.

    Can auto-extract FPS and duration from video, or use manual configuration.

    Config:
        video_path: (Optional) Video file to extract FPS and duration from
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
    ctx.logger.info(f"Start time: {config.start_time} -> {start_timestamp_ms} ms")

    # Get FPS and total_frames from video or config
    if config.video_path:
        video_path = ctx.resolve_path(config.video_path)
        ctx.logger.info(f"Extracting metadata from video: {video_path}")

        video_meta = get_video_metadata(video_path)
        fps = video_meta["fps"]
        total_frames = video_meta["total_frames"]

        ctx.logger.info(
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
        ctx.logger.info(f"Using manual config: {total_frames} frames at {fps} FPS")

    timeline = generate_timeline_with_jitter(
        fps=fps,
        total_frames=total_frames,
        start_timestamp_ms=start_timestamp_ms,
        jitter_ms=config.jitter_ms,
        random_seed=config.random_seed,
    )

    output_path = ctx.resolve_path(config.output_csv)
    save_timeline_csv(timeline, output_path)

    ctx.logger.info(f"Timeline saved to {output_path}")
    ctx.logger.info(
        f"Time range: {timeline[0]['timestamp_ms']:.1f} - {timeline[-1]['timestamp_ms']:.1f} ms"
    )

    # Store in context for other plugins
    ctx.remember("timeline_path", output_path)
    ctx.remember("start_timestamp_ms", start_timestamp_ms)
    ctx.remember("video_duration_s", (total_frames / fps) if fps > 0 else 0)

    return output_path


class SpeedDataGeneratorConfig(PluginConfig):
    start_time: Optional[str] = None  # Time format like "2025-10-27 00:00:00"
    video_path: Optional[str] = None  # Optional: auto-extract duration from video
    duration_s: Optional[float] = None  # Required if video_path not provided
    max_interval_s: float = 5.0
    speed_change_threshold: float = 2.0
    output_jsonl: str = "output/speed.jsonl"
    random_seed: Optional[int] = None
    use_default_profile: bool = True
    custom_profiles: Optional[list] = None


@plugin(name="Speed Data Generator", config=SpeedDataGeneratorConfig)
def generate_speed_data(ctx: PluginContext) -> Any:
    """
    Generate event-driven speed data.

    Speed is recorded only when:
    1. Speed changes by more than threshold (default 2 km/h)
    2. At least max_interval_s has elapsed (default 5s)

    Mimics real sensor behavior: event-driven with periodic updates.
    Data generation is INDEPENDENT of video duration.

    Config:
        start_time: Starting time string (e.g., "2025-10-27 00:00:00")
                    If not provided, uses context from Timeline Generator
        video_path: (Optional) Video to extract duration from
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
        ctx.logger.info(f"Start time: {config.start_time} -> {start_timestamp_ms} ms")
    elif hasattr(ctx, 'recall') and ctx.recall("start_timestamp_ms"):
        start_timestamp_ms = ctx.recall("start_timestamp_ms")
        ctx.logger.info(f"Using start_timestamp_ms from context: {start_timestamp_ms}")
    else:
        raise ValueError("start_time must be provided or Timeline Generator must run first")

    # Get duration from video or config or context
    if config.video_path:
        video_path = ctx.resolve_path(config.video_path)
        video_meta = get_video_metadata(video_path)
        duration_s = video_meta["duration_s"]
        ctx.logger.info(f"Using video duration: {duration_s:.2f}s from {video_path}")
    elif config.duration_s is not None:
        duration_s = config.duration_s
        ctx.logger.info(f"Using configured duration: {duration_s}s")
    elif hasattr(ctx, 'recall') and ctx.recall("video_duration_s"):
        duration_s = ctx.recall("video_duration_s")
        ctx.logger.info(f"Using duration from context: {duration_s:.2f}s")
    else:
        raise ValueError("duration_s or video_path must be provided")

    ctx.logger.info(
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

    ctx.logger.info(f"Generated {len(speed_data)} speed events")
    ctx.logger.info(f"Speed data saved to {output_path}")

    if speed_data:
        speeds = [d["speed"] for d in speed_data]
        ctx.logger.info(f"Speed range: {min(speeds):.1f} - {max(speeds):.1f} km/h")

    return output_path


class ADBTargetGeneratorConfig(PluginConfig):
    start_time: Optional[str] = None  # Time format like "2025-10-27 00:00:00"
    video_path: Optional[str] = None  # Optional: auto-extract duration from video
    duration_s: Optional[float] = None  # Required if video_path not provided
    frequency_hz: float = 20.0
    timing_jitter_ms: int = 2  # Integer milliseconds for realistic timing variation
    num_targets: int = 3
    ego_speed_kmh: float = 60.0
    output_jsonl: str = "output/targets.jsonl"
    random_seed: Optional[int] = None


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

    Config:
        start_time: Starting time string (e.g., "2025-10-27 00:00:00")
                    If not provided, uses context from Timeline Generator
        video_path: (Optional) Video to extract duration from
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
        ctx.logger.info(f"Start time: {config.start_time} -> {start_timestamp_ms} ms")
    elif hasattr(ctx, 'recall') and ctx.recall("start_timestamp_ms"):
        start_timestamp_ms = ctx.recall("start_timestamp_ms")
        ctx.logger.info(f"Using start_timestamp_ms from context: {start_timestamp_ms}")
    else:
        raise ValueError("start_time must be provided or Timeline Generator must run first")

    # Get duration from video or config or context
    if config.video_path:
        video_path = ctx.resolve_path(config.video_path)
        video_meta = get_video_metadata(video_path)
        duration_s = video_meta["duration_s"]
        ctx.logger.info(f"Using video duration: {duration_s:.2f}s from {video_path}")
    elif config.duration_s is not None:
        duration_s = config.duration_s
        ctx.logger.info(f"Using configured duration: {duration_s}s")
    elif hasattr(ctx, 'recall') and ctx.recall("video_duration_s"):
        duration_s = ctx.recall("video_duration_s")
        ctx.logger.info(f"Using duration from context: {duration_s:.2f}s")
    else:
        raise ValueError("duration_s or video_path must be provided")

    ctx.logger.info(
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

    ctx.logger.info(f"Generated {len(target_data)} target frames")
    ctx.logger.info(f"Target data saved to {output_path}")

    # Statistics
    total_targets = sum(len(d["targets"]) for d in target_data)
    avg_targets = total_targets / len(target_data) if target_data else 0
    ctx.logger.info(f"Average targets per frame: {avg_targets:.1f}")


# =============================================================================
# Synthetic Video Generation Plugin
# =============================================================================


class SyntheticVideoGeneratorConfig(PluginConfig):
    output_path: str = "input/synthetic_driving.mp4"
    duration_s: float = 60.0
    fps: float = 30.0
    width: int = 1920
    height: int = 1080
    speed_kmh: float = 60.0
    random_seed: Optional[int] = None


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

    ctx.logger.info(
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

    ctx.logger.info(f"Video saved to {output_path}")
    ctx.logger.info(
        f"Generated {metadata['total_frames']} frames "
        f"({metadata['duration_s']}s at {metadata['fps']} FPS)"
    )

    # Save video metadata to context for downstream plugins
    ctx.remember("video_fps", metadata["fps"])
    ctx.remember("video_total_frames", metadata["total_frames"])
    ctx.remember("video_duration_s", metadata["duration_s"])

    return metadata

