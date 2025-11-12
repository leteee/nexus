"""
Video processing utilities for frame extraction and composition.

Provides functions to split videos into frames and compose frames back into video.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Any, Callable, Dict

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from .types import VideoMetadata
from .io import load_frame_timestamps

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: Path,
    output_path: Path,
    *,
    frame_pattern: str = "frame_{:06d}.png",
) -> VideoMetadata:
    """
    Extract all frames from video and save as images.

    Args:
        video_path: Path to input video file
        output_path: Directory to save extracted frames
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
    output_path = Path(output_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    output_path.mkdir(parents=True, exist_ok=True)

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

        with tqdm(total=total_frames, desc="Extracting frames", unit="frame") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Save frame
                frame_path = output_path / frame_pattern.format(frame_idx)
                cv2.imwrite(str(frame_path), frame)

                frame_idx += 1
                pbar.update(1)

        logger.info(f"Completed: extracted {frame_idx} frames to {output_path}")

        return VideoMetadata(
            total_frames=frame_idx,
            fps=fps,
            width=width,
            height=height,
            output_path=output_path,
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
        with tqdm(total=len(frame_files), desc="Composing video", unit="frame") as pbar:
            for idx, frame_path in enumerate(frame_files):
                frame = cv2.imread(str(frame_path))
                if frame is None:
                    logger.warning(f"Failed to read frame: {frame_path}, skipping")
                    continue

                writer.write(frame)
                pbar.update(1)

        logger.info(f"Completed: created video at {output_path}")
        return output_path

    finally:
        writer.release()


def render_all_frames(
    frames_dir: Path,
    output_path: Path,
    timestamps_path: Path,
    renderer_configs: List[dict],
    *,
    frame_pattern: str = "frame_{:06d}.png",
    start_time_ms: Optional[float] = None,
    end_time_ms: Optional[float] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    ctx: Any,
) -> Path:
    """
    Apply multiple data renderers to all video frames.

    Dynamically imports and instantiates renderer classes by full qualified name.
    Renderers are instantiated once and reused for all frames.

    Args:
        frames_dir: Directory containing extracted frames
        output_path: Directory for rendered frames
        timestamps_path: Path to frame timestamps CSV
        renderer_configs: List of renderer configurations
            Format: [{"class": "full.module.path.ClassName", "kwargs": {...}}, ...]
            - "class": Full qualified class name (e.g., "nexus.contrib.repro.renderers.SpeedRenderer")
            - "kwargs": Dictionary of renderer constructor arguments
        frame_pattern: Frame filename pattern
        start_time_ms: Optional start time (None=from beginning)
        end_time_ms: Optional end time (None=to end)
        progress_callback: Optional callback(count, total) for progress tracking
        ctx: Context object to pass to renderers (required, with logger and path resolution)

    Returns:
        Path to output directory

    Note:
        To display frame info, add FrameInfoRenderer to renderer_configs:
        {
            "class": "nexus.contrib.repro.renderers.FrameInfoRenderer",
            "kwargs": {
                "position": [10, 30],
                "format": "datetime"
            }
        }

    Example:
        >>> # Using full class names
        >>> renderer_configs = [
        ...     {
        ...         "class": "nexus.contrib.repro.renderers.FrameInfoRenderer",
        ...         "kwargs": {
        ...             "position": (10, 30),
        ...             "format": "datetime"
        ...         }
        ...     },
        ...     {
        ...         "class": "nexus.contrib.repro.renderers.SpeedRenderer",
        ...         "kwargs": {
        ...             "data_path": Path("speed.jsonl"),
        ...             "position": (30, 60),
        ...             "time_offset_ms": 0
        ...         }
        ...     },
        ...     {
        ...         "class": "nexus.contrib.repro.renderers.TargetRenderer",
        ...         "kwargs": {
        ...             "data_path": Path("targets.jsonl"),
        ...             "calibration_path": Path("calib.yaml"),
        ...             "time_offset_ms": -50
        ...         }
        ...     }
        ... ]
        >>> render_all_frames(
        ...     Path("frames/"),
        ...     Path("rendered/"),
        ...     Path("timestamps.csv"),
        ...     renderer_configs,
        ...     start_time_ms=1000.0,
        ...     end_time_ms=5000.0,
        ...     ctx=ctx
        ... )
    """
    import importlib

    frames_dir = Path(frames_dir)
    output_path = Path(output_path)
    timestamps_path = Path(timestamps_path)

    # Validate inputs
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")
    if not timestamps_path.exists():
        raise FileNotFoundError(f"Timestamps file not found: {timestamps_path}")

    output_path.mkdir(parents=True, exist_ok=True)

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
        return output_path

    # Instantiate all renderers once
    logger.info(f"Preparing {len(renderer_configs)} renderers")
    renderers: List[Dict[str, Any]] = []

    for i, config in enumerate(renderer_configs):
        # Extract full class name
        class_path = config.get("class")
        if not class_path:
            raise ValueError(
                f"Renderer config must have 'class' key with full qualified class name: {config}"
            )

        # Dynamically import renderer class
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            renderer_class = getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            raise ImportError(
                f"Failed to import renderer class '{class_path}': {e}"
            )

        renderer_kwargs = config.get("kwargs", {})

        # Instantiate renderer with ctx as first parameter
        renderer_instance = renderer_class(ctx, **renderer_kwargs)

        renderers.append({
            "class": class_path,
            "instance": renderer_instance
        })

        logger.info(f"  [{i+1}] {class_path} -> {renderer_class.__name__}")

    # Render all frames
    logger.info(f"Rendering {len(frame_times)} frames...")
    rendered_count = 0
    total_frames = len(frame_times)

    with tqdm(total=total_frames, desc="Rendering frames", unit="frame", disable=progress_callback is not None) as pbar:
        for _, row in frame_times.iterrows():
            frame_idx = int(row["frame_index"])
            timestamp_ms = int(row["timestamp_ms"])

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
            for renderer_info in renderers:
                renderer_instance = renderer_info["instance"]
                renderer_class_name = renderer_info["class"]

                # Special handling for FrameInfoRenderer: pass frame_idx
                if "FrameInfoRenderer" in renderer_class_name:
                    frame = renderer_instance.render(frame, timestamp_ms, frame_idx)
                else:
                    frame = renderer_instance.render(frame, timestamp_ms)

            # Save rendered frame
            output_file = output_path / frame_pattern.format(frame_idx)
            cv2.imwrite(str(output_file), frame)

            rendered_count += 1

            # Progress reporting
            if progress_callback:
                progress_callback(rendered_count, total_frames)
            else:
                pbar.update(1)

    logger.info(f"Completed: rendered {rendered_count} frames to {output_path}")

    return output_path
