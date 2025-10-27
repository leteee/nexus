"""
Nexus plugin adapters for repro (data replay) module.

Adapts video replay and data rendering logic to Nexus plugin interface.
"""

from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

from nexus.contrib.repro.video import extract_frames, compose_video


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
    renderer_class: str  # e.g., "nexus.contrib.repro.examples.SimpleTextRenderer"
    renderer_kwargs: dict = {}  # Additional args for renderer __init__


@plugin(name="Data Renderer", config=DataRendererConfig)
def render_data_on_frames(ctx):
    """
    Apply custom data renderer to all video frames.

    Dynamically loads user-defined renderer class and processes frames.

    Config:
        frames_dir: Directory containing extracted frames
        output_dir: Directory for rendered frames
        frame_pattern: Frame filename pattern
        renderer_class: Fully-qualified class name
        renderer_kwargs: Arguments for renderer initialization

    Example config:
        renderer_class: "nexus.contrib.repro.examples.SimpleTextRenderer"
        renderer_kwargs:
            data_path: "data/speed.jsonl"
            value_key: "speed"
            label: "Speed (km/h)"
            position: [20, 50]
    """
    import importlib

    from pathlib import Path

    frames_dir = ctx.resolve_path(ctx.config.frames_dir)
    output_dir = ctx.resolve_path(ctx.config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load frame timestamps
    from nexus.contrib.repro.types import load_frame_timestamps

    timestamps_path = frames_dir / "frame_timestamps.csv"
    if not timestamps_path.exists():
        raise FileNotFoundError(
            f"Frame timestamps not found: {timestamps_path}. "
            "Run Video Splitter first."
        )

    frame_times = load_frame_timestamps(timestamps_path)

    # Dynamically import renderer class
    module_path, class_name = ctx.config.renderer_class.rsplit(".", 1)
    module = importlib.import_module(module_path)
    RendererClass = getattr(module, class_name)

    ctx.logger.info(f"Loaded renderer: {ctx.config.renderer_class}")

    # Resolve paths in renderer_kwargs
    renderer_kwargs = ctx.config.renderer_kwargs.copy()
    if "data_path" in renderer_kwargs:
        renderer_kwargs["data_path"] = ctx.resolve_path(
            renderer_kwargs["data_path"]
        )

    # Initialize renderer
    renderer = RendererClass(**renderer_kwargs)

    ctx.logger.info(f"Rendering {len(frame_times)} frames...")

    import cv2

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

        # Match data and render
        data = renderer.match_data(timestamp_ms, tolerance_ms=50.0)
        rendered_frame = renderer.render(frame, data)

        # Save rendered frame
        output_path = output_dir / ctx.config.frame_pattern.format(frame_idx)
        cv2.imwrite(str(output_path), rendered_frame)

        rendered_count += 1

        if (rendered_count) % 100 == 0:
            ctx.logger.info(f"Rendered {rendered_count} frames...")

    ctx.logger.info(
        f"Completed: rendered {rendered_count} frames to {output_dir}"
    )

    # Store output dir for Video Composer
    ctx.remember("rendered_frames_dir", output_dir)

    return output_dir
