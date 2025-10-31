"""
Nexus plugin adapters for repro (data replay) module.

Adapts video replay and data rendering logic to Nexus plugin interface.
"""

from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

from nexus.contrib.repro.video import extract_frames, compose_video
from nexus.contrib.repro.datagen import (
    generate_timeline_with_jitter,
    generate_speed_data_event_driven,
    generate_adb_target_data,
    save_jsonl,
    save_timeline_csv,
    parse_time_string,
    get_video_metadata,
    SpeedProfile,
)


# =============================================================================
# Video Processing Plugins
# =============================================================================


class VideoSplitterConfig(PluginConfig):
    video_path: str
    output_dir: str = "frames"
    frame_pattern: str = "frame_{:06d}.png"
    save_timestamps: bool = True


class VideoComposerConfig(PluginConfig):
    frames_dir: str = "frames"
    output_path: str = "output.mp4"
    fps: float = 30.0
    frame_pattern: str = "frame_{:06d}.png"
    codec: str = "mp4v"
    start_frame: int = 0
    end_frame: int | None = None


@plugin(name="Video Splitter", config=VideoSplitterConfig)
def split_video_to_frames(ctx):
    """
    Extract all frames from video and save as images.

    Creates:
    - Individual frame images (PNG format)
    - frame_timestamps.csv mapping frames to physical time

    Output stored in shared context for downstream plugins.
    """
    video_path = ctx.resolve_path(ctx.config.video_path)
    output_dir = ctx.resolve_path(ctx.config.output_dir)

    ctx.logger.info(f"Extracting frames from {video_path}")

    metadata = extract_frames(
        video_path,
        output_dir,
        frame_pattern=ctx.config.frame_pattern,
        save_timestamps=ctx.config.save_timestamps,
    )

    ctx.logger.info(
        f"Extracted {metadata.total_frames} frames at {metadata.fps:.2f} FPS"
    )

    # Store metadata for downstream plugins
    ctx.remember("video_metadata", metadata)
    ctx.remember("frames_dir", output_dir)

    return metadata


@plugin(name="Video Composer", config=VideoComposerConfig)
def compose_frames_to_video(ctx):
    """
    Compose video from sequence of frame images.

    Can use frames from Video Splitter or custom rendered frames.
    Supports frame range selection for creating clips.
    """
    frames_dir = ctx.resolve_path(ctx.config.frames_dir)
    output_path = ctx.resolve_path(ctx.config.output_path)

    ctx.logger.info(f"Composing video from {frames_dir}")

    result_path = compose_video(
        frames_dir,
        output_path,
        fps=ctx.config.fps,
        frame_pattern=ctx.config.frame_pattern,
        codec=ctx.config.codec,
        start_frame=ctx.config.start_frame,
        end_frame=ctx.config.end_frame,
    )

    ctx.logger.info(f"Created video: {result_path}")

    ctx.remember("output_video", result_path)

    return result_path


# =============================================================================
# Data Rendering Plugin
# =============================================================================


class DataRendererConfig(PluginConfig):
    frames_dir: str = "frames"
    output_dir: str = "rendered_frames"
    frame_pattern: str = "frame_{:06d}.png"
    timestamps_path: str | None = None  # Optional: custom timestamps CSV path
    renderers: list[dict]  # List of {"class": "...", "kwargs": {...}}


@plugin(name="Data Renderer", config=DataRendererConfig)
def render_data_on_frames(ctx):
    """
    Apply multiple data renderers to all video frames.

    Each renderer is applied sequentially to render different data types.

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
        renderers: List of renderer configurations
    """
    import importlib
    from pathlib import Path
    import cv2

    frames_dir = ctx.resolve_path(ctx.config.frames_dir)
    output_dir = ctx.resolve_path(ctx.config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load frame timestamps
    from nexus.contrib.repro.types import load_frame_timestamps

    if ctx.config.timestamps_path:
        timestamps_path = ctx.resolve_path(ctx.config.timestamps_path)
    else:
        timestamps_path = frames_dir / "frame_timestamps.csv"

    if not timestamps_path.exists():
        raise FileNotFoundError(
            f"Frame timestamps not found: {timestamps_path}. "
            "Run Video Splitter first or specify timestamps_path in config."
        )

    frame_times = load_frame_timestamps(timestamps_path)

    # Load all renderers
    def load_renderer(class_path: str, kwargs: dict):
        """Load renderer class and instantiate with kwargs."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        RendererClass = getattr(module, class_name)

        # Resolve paths in kwargs
        resolved_kwargs = kwargs.copy()
        for key in ["data_path", "calibration_path"]:
            if key in resolved_kwargs:
                resolved_kwargs[key] = ctx.resolve_path(resolved_kwargs[key])

        return RendererClass(**resolved_kwargs)

    ctx.logger.info(f"Loading {len(ctx.config.renderers)} renderers")
    renderers = []
    for i, renderer_config in enumerate(ctx.config.renderers):
        renderer_class = renderer_config["class"]
        renderer_kwargs = renderer_config.get("kwargs", {})
        renderer = load_renderer(renderer_class, renderer_kwargs)
        renderers.append(renderer)
        ctx.logger.info(f"  [{i+1}] {renderer_class}")

    ctx.logger.info(f"Rendering {len(frame_times)} frames...")

    rendered_count = 0

    for _, row in frame_times.iterrows():
        frame_idx = int(row["frame_index"])
        timestamp_ms = row["timestamp_ms"]

        # Load frame
        frame_path = frames_dir / ctx.config.frame_pattern.format(frame_idx)
        if not frame_path.exists():
            ctx.logger.warning(f"Frame not found: {frame_path}, skipping")
            continue

        frame = cv2.imread(str(frame_path))
        if frame is None:
            ctx.logger.warning(f"Failed to read frame: {frame_path}")
            continue

        # Apply all renderers sequentially
        for renderer in renderers:
            frame = renderer.render(frame, timestamp_ms)

        # Save rendered frame
        output_path = output_dir / ctx.config.frame_pattern.format(frame_idx)
        cv2.imwrite(str(output_path), frame)

        rendered_count += 1

        if (rendered_count) % 100 == 0:
            ctx.logger.info(f"Rendered {rendered_count} frames...")

    ctx.logger.info(
        f"Completed: rendered {rendered_count} frames to {output_dir}"
    )

    # Store output dir for Video Composer
    ctx.remember("rendered_frames_dir", output_dir)

    return output_dir


# =============================================================================
# Data Generation Plugins
# =============================================================================


class TimelineGeneratorConfig(PluginConfig):
    video_path: str | None = None  # Optional: auto-extract FPS and duration from video
    fps: float | None = None  # Required if video_path not provided
    total_frames: int | None = None  # Required if video_path not provided
    start_time: str = "2025-10-27 00:00:00"  # Time format (converted to timestamp)
    jitter_ms: float = 1.5
    output_csv: str = "output/timeline.csv"
    random_seed: int | None = None


@plugin(name="Timeline Generator", config=TimelineGeneratorConfig)
def generate_timeline(ctx):
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
    # Parse start time to timestamp
    start_timestamp_ms = parse_time_string(ctx.config.start_time)
    ctx.logger.info(f"Start time: {ctx.config.start_time} -> {start_timestamp_ms} ms")

    # Get FPS and total_frames from video or config
    if ctx.config.video_path:
        video_path = ctx.resolve_path(ctx.config.video_path)
        ctx.logger.info(f"Extracting metadata from video: {video_path}")

        video_meta = get_video_metadata(video_path)
        fps = video_meta["fps"]
        total_frames = video_meta["total_frames"]

        ctx.logger.info(
            f"Video: {total_frames} frames at {fps:.2f} FPS "
            f"(duration: {video_meta['duration_s']:.2f}s)"
        )
    else:
        if ctx.config.fps is None or ctx.config.total_frames is None:
            raise ValueError(
                "Either video_path or both fps and total_frames must be provided"
            )
        fps = ctx.config.fps
        total_frames = ctx.config.total_frames
        ctx.logger.info(f"Using manual config: {total_frames} frames at {fps} FPS")

    timeline = generate_timeline_with_jitter(
        fps=fps,
        total_frames=total_frames,
        start_timestamp_ms=start_timestamp_ms,
        jitter_ms=ctx.config.jitter_ms,
        random_seed=ctx.config.random_seed,
    )

    output_path = ctx.resolve_path(ctx.config.output_csv)
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
    start_time: str | None = None  # Time format like "2025-10-27 00:00:00"
    video_path: str | None = None  # Optional: auto-extract duration from video
    duration_s: float | None = None  # Required if video_path not provided
    max_interval_s: float = 5.0
    speed_change_threshold: float = 2.0
    output_jsonl: str = "output/speed.jsonl"
    random_seed: int | None = None
    use_default_profile: bool = True
    custom_profiles: list | None = None


@plugin(name="Speed Data Generator", config=SpeedDataGeneratorConfig)
def generate_speed_data(ctx):
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
    # Get start timestamp from config or context
    if ctx.config.start_time:
        start_timestamp_ms = parse_time_string(ctx.config.start_time)
        ctx.logger.info(f"Start time: {ctx.config.start_time} -> {start_timestamp_ms} ms")
    elif hasattr(ctx, 'recall') and ctx.recall("start_timestamp_ms"):
        start_timestamp_ms = ctx.recall("start_timestamp_ms")
        ctx.logger.info(f"Using start_timestamp_ms from context: {start_timestamp_ms}")
    else:
        raise ValueError("start_time must be provided or Timeline Generator must run first")

    # Get duration from video or config or context
    if ctx.config.video_path:
        video_path = ctx.resolve_path(ctx.config.video_path)
        video_meta = get_video_metadata(video_path)
        duration_s = video_meta["duration_s"]
        ctx.logger.info(f"Using video duration: {duration_s:.2f}s from {video_path}")
    elif ctx.config.duration_s is not None:
        duration_s = ctx.config.duration_s
        ctx.logger.info(f"Using configured duration: {duration_s}s")
    elif hasattr(ctx, 'recall') and ctx.recall("video_duration_s"):
        duration_s = ctx.recall("video_duration_s")
        ctx.logger.info(f"Using duration from context: {duration_s:.2f}s")
    else:
        raise ValueError("duration_s or video_path must be provided")

    ctx.logger.info(
        f"Generating speed data: {duration_s}s, "
        f"event threshold: {ctx.config.speed_change_threshold} km/h, "
        f"max interval: {ctx.config.max_interval_s}s"
    )

    speed_data = generate_speed_data_event_driven(
        start_timestamp_ms=start_timestamp_ms,
        duration_s=duration_s,
        speed_profiles=None if ctx.config.use_default_profile else ctx.config.custom_profiles,
        max_interval_s=ctx.config.max_interval_s,
        speed_change_threshold=ctx.config.speed_change_threshold,
        random_seed=ctx.config.random_seed,
    )

    output_path = ctx.resolve_path(ctx.config.output_jsonl)
    save_jsonl(speed_data, output_path)

    ctx.logger.info(f"Generated {len(speed_data)} speed events")
    ctx.logger.info(f"Speed data saved to {output_path}")

    if speed_data:
        speeds = [d["speed"] for d in speed_data]
        ctx.logger.info(f"Speed range: {min(speeds):.1f} - {max(speeds):.1f} km/h")

    return output_path


class ADBTargetGeneratorConfig(PluginConfig):
    start_time: str | None = None  # Time format like "2025-10-27 00:00:00"
    video_path: str | None = None  # Optional: auto-extract duration from video
    duration_s: float | None = None  # Required if video_path not provided
    frequency_hz: float = 20.0
    timing_jitter_ms: float = 2.0  # Reception timing error
    num_targets: int = 3
    ego_speed_kmh: float = 60.0
    output_jsonl: str = "output/targets.jsonl"
    random_seed: int | None = None


@plugin(name="ADB Target Generator", config=ADBTargetGeneratorConfig)
def generate_adb_targets(ctx):
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
    # Get start timestamp from config or context
    if ctx.config.start_time:
        start_timestamp_ms = parse_time_string(ctx.config.start_time)
        ctx.logger.info(f"Start time: {ctx.config.start_time} -> {start_timestamp_ms} ms")
    elif hasattr(ctx, 'recall') and ctx.recall("start_timestamp_ms"):
        start_timestamp_ms = ctx.recall("start_timestamp_ms")
        ctx.logger.info(f"Using start_timestamp_ms from context: {start_timestamp_ms}")
    else:
        raise ValueError("start_time must be provided or Timeline Generator must run first")

    # Get duration from video or config or context
    if ctx.config.video_path:
        video_path = ctx.resolve_path(ctx.config.video_path)
        video_meta = get_video_metadata(video_path)
        duration_s = video_meta["duration_s"]
        ctx.logger.info(f"Using video duration: {duration_s:.2f}s from {video_path}")
    elif ctx.config.duration_s is not None:
        duration_s = ctx.config.duration_s
        ctx.logger.info(f"Using configured duration: {duration_s}s")
    elif hasattr(ctx, 'recall') and ctx.recall("video_duration_s"):
        duration_s = ctx.recall("video_duration_s")
        ctx.logger.info(f"Using duration from context: {duration_s:.2f}s")
    else:
        raise ValueError("duration_s or video_path must be provided")

    ctx.logger.info(
        f"Generating ADB target data: {duration_s}s at {ctx.config.frequency_hz}Hz, "
        f"{ctx.config.num_targets} targets, timing jitter: ±{ctx.config.timing_jitter_ms}ms"
    )

    target_data = generate_adb_target_data(
        start_timestamp_ms=start_timestamp_ms,
        duration_s=duration_s,
        frequency_hz=ctx.config.frequency_hz,
        num_targets=ctx.config.num_targets,
        ego_speed_kmh=ctx.config.ego_speed_kmh,
        timing_jitter_ms=ctx.config.timing_jitter_ms,
        random_seed=ctx.config.random_seed,
    )

    output_path = ctx.resolve_path(ctx.config.output_jsonl)
    save_jsonl(target_data, output_path)

    ctx.logger.info(f"Generated {len(target_data)} target frames")
    ctx.logger.info(f"Target data saved to {output_path}")

    # Statistics
    total_targets = sum(len(d["targets"]) for d in target_data)
    avg_targets = total_targets / len(target_data) if target_data else 0
    ctx.logger.info(f"Average targets per frame: {avg_targets:.1f}")

    return output_path
