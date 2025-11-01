"""
Video processing utilities for frame extraction and composition.

Provides functions to split videos into frames and compose frames back into video.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Optional, List, Any

import cv2
import numpy as np
import pandas as pd

from .types import VideoMetadata
from .io import load_frame_timestamps

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: Path,
    output_dir: Path,
    *,
    frame_pattern: str = "frame_{:06d}.png",
) -> VideoMetadata:
    """
    Extract all frames from video and save as images.

    Args:
        video_path: Path to input video file
        output_dir: Directory to save extracted frames
        frame_pattern: Filename pattern for frames (must contain one format spec)

    Returns:
        VideoMetadata with extraction info

    Example:
        >>> metadata = extract_frames(
        ...     Path("input.mp4"),
        ...     Path("frames/"),
        ...     frame_pattern="frame_{:06d}.png"
        ... )
        >>> print(f"Extracted {metadata.total_frames} frames at {metadata.fps} FPS")
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    try:
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(
            f"Video: {total_frames} frames, {fps:.2f} FPS, {width}x{height}"
        )

        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Save frame
            frame_path = output_dir / frame_pattern.format(frame_idx)
            cv2.imwrite(str(frame_path), frame)

            if (frame_idx + 1) % 100 == 0:
                logger.info(f"Extracted {frame_idx + 1} frames...")

            frame_idx += 1

        logger.info(f"Completed: extracted {frame_idx} frames to {output_dir}")

        return VideoMetadata(
            total_frames=frame_idx,
            fps=fps,
            width=width,
            height=height,
            output_dir=output_dir,
        )

    finally:
        cap.release()


def compose_video(
    frames_dir: Path,
    output_path: Path,
    *,
    fps: float = 30.0,
    frame_pattern: str = "frame_{:06d}.png",
    codec: str = "mp4v",
    start_frame: int = 0,
    end_frame: Optional[int] = None,
) -> Path:
    """
    Compose video from sequence of frame images.

    Args:
        frames_dir: Directory containing frame images
        output_path: Path for output video file
        fps: Frames per second for output video
        frame_pattern: Filename pattern for frames
        codec: FourCC codec code (e.g., 'mp4v', 'XVID', 'H264')
        start_frame: First frame index to include
        end_frame: Last frame index (None = all frames)

    Returns:
        Path to created video file

    Example:
        >>> compose_video(
        ...     Path("frames/"),
        ...     Path("output.mp4"),
        ...     fps=30.0,
        ...     frame_pattern="frame_{:06d}.png"
        ... )
    """
    frames_dir = Path(frames_dir)
    output_path = Path(output_path)

    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Find all frames
    frame_files = sorted(frames_dir.glob(frame_pattern.replace("{:06d}", "*")))
    if not frame_files:
        raise FileNotFoundError(f"No frames found in {frames_dir}")

    # Filter by frame range
    if end_frame is not None:
        frame_files = frame_files[start_frame : end_frame + 1]
    else:
        frame_files = frame_files[start_frame:]

    if not frame_files:
        raise ValueError(f"No frames in range {start_frame}-{end_frame}")

    logger.info(f"Composing video from {len(frame_files)} frames at {fps} FPS")

    # Read first frame to get dimensions
    first_frame = cv2.imread(str(frame_files[0]))
    if first_frame is None:
        raise RuntimeError(f"Failed to read frame: {frame_files[0]}")

    height, width = first_frame.shape[:2]

    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(
        str(output_path),
        fourcc,
        fps,
        (width, height),
    )

    if not writer.isOpened():
        raise RuntimeError(f"Failed to create video writer: {output_path}")

    try:
        for idx, frame_path in enumerate(frame_files):
            frame = cv2.imread(str(frame_path))
            if frame is None:
                logger.warning(f"Failed to read frame: {frame_path}, skipping")
                continue

            writer.write(frame)

            if (idx + 1) % 100 == 0:
                logger.info(f"Composed {idx + 1} frames...")

        logger.info(f"Completed: created video at {output_path}")
        return output_path

    finally:
        writer.release()


def render_all_frames(
    frames_dir: Path,
    output_dir: Path,
    timestamps_path: Path,
    renderer_configs: List[dict],
    *,
    frame_pattern: str = "frame_{:06d}.png",
    start_time_ms: Optional[float] = None,
    end_time_ms: Optional[float] = None,
    progress_callback: Optional[callable] = None,
) -> Path:
    """
    Apply multiple data renderers to all video frames.

    This is the core rendering function that handles:
    1. Loading frame timestamps
    2. Filtering by time range (if specified)
    3. Instantiating renderer classes from configs
    4. Iterating through frames
    5. Applying renderers sequentially
    6. Saving rendered frames

    Time is first-class: Video timeline is the primary timeline.
    All data lines sync to video timeline.

    Args:
        frames_dir: Directory containing extracted frames
        output_dir: Directory for rendered frames
        timestamps_path: Path to frame timestamps CSV
        renderer_configs: List of renderer configurations
            Format: [{"class": "module.ClassName", "kwargs": {...}}, ...]
        frame_pattern: Frame filename pattern
        start_time_ms: Optional start time (None=from beginning)
        end_time_ms: Optional end time (None=to end)
        progress_callback: Optional callback(count, total) for progress tracking

    Returns:
        Path to output directory

    Example:
        >>> renderer_configs = [
        ...     {
        ...         "class": "nexus.contrib.repro.renderers.SpeedRenderer",
        ...         "kwargs": {
        ...             "data_path": Path("speed.jsonl"),
        ...             "position": (30, 60),
        ...             "time_offset_ms": 0  # No time offset
        ...         }
        ...     },
        ...     {
        ...         "class": "nexus.contrib.repro.renderers.TargetRenderer",
        ...         "kwargs": {
        ...             "data_path": Path("targets.jsonl"),
        ...             "time_offset_ms": -50  # Data 50ms ahead
        ...         }
        ...     }
        ... ]
        >>> render_all_frames(
        ...     Path("frames/"),
        ...     Path("rendered/"),
        ...     Path("timestamps.csv"),
        ...     renderer_configs,
        ...     start_time_ms=1000.0,  # Start at 1 second
        ...     end_time_ms=5000.0     # End at 5 seconds
        ... )
    """
    frames_dir = Path(frames_dir)
    output_dir = Path(output_dir)
    timestamps_path = Path(timestamps_path)

    # Validate inputs
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")
    if not timestamps_path.exists():
        raise FileNotFoundError(f"Timestamps file not found: {timestamps_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load frame timestamps
    logger.info(f"Loading frame timestamps from {timestamps_path}")
    frame_times = load_frame_timestamps(timestamps_path)

    # Filter by time range if specified
    if start_time_ms is not None:
        frame_times = frame_times[frame_times["timestamp_ms"] >= start_time_ms]
        logger.info(f"Filtered frames: start_time >= {start_time_ms} ms")

    if end_time_ms is not None:
        frame_times = frame_times[frame_times["timestamp_ms"] <= end_time_ms]
        logger.info(f"Filtered frames: end_time <= {end_time_ms} ms")

    if len(frame_times) == 0:
        logger.warning("No frames in specified time range")
        return output_dir

    # Load and instantiate all renderers
    def load_renderer(class_path: str, kwargs: dict) -> Any:
        """Dynamically load renderer class and instantiate."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        RendererClass = getattr(module, class_name)
        return RendererClass(**kwargs)

    logger.info(f"Loading {len(renderer_configs)} renderers")
    renderers = []
    for i, config in enumerate(renderer_configs):
        renderer_class = config["class"]
        renderer_kwargs = config.get("kwargs", {})
        renderer = load_renderer(renderer_class, renderer_kwargs)
        renderers.append(renderer)
        logger.info(f"  [{i+1}] {renderer_class}")

    # Render all frames
    logger.info(f"Rendering {len(frame_times)} frames...")
    rendered_count = 0
    total_frames = len(frame_times)

    for _, row in frame_times.iterrows():
        frame_idx = int(row["frame_index"])
        timestamp_ms = row["timestamp_ms"]

        # Load frame
        frame_path = frames_dir / frame_pattern.format(frame_idx)
        if not frame_path.exists():
            logger.warning(f"Frame not found: {frame_path}, skipping")
            continue

        frame = cv2.imread(str(frame_path))
        if frame is None:
            logger.warning(f"Failed to read frame: {frame_path}")
            continue

        # Apply all renderers sequentially
        for renderer in renderers:
            frame = renderer.render(frame, timestamp_ms)

        # Save rendered frame
        output_path = output_dir / frame_pattern.format(frame_idx)
        cv2.imwrite(str(output_path), frame)

        rendered_count += 1

        # Progress reporting
        if progress_callback:
            progress_callback(rendered_count, total_frames)
        elif rendered_count % 100 == 0:
            logger.info(f"Rendered {rendered_count}/{total_frames} frames...")

    logger.info(f"Completed: rendered {rendered_count} frames to {output_dir}")

    return output_dir
