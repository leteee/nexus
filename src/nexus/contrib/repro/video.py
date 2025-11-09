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


def _draw_frame_info(
    frame: np.ndarray,
    frame_idx: int,
    timestamp_ms: int,
) -> np.ndarray:
    """
    Draw frame information overlay (frame ID + timestamp) in top-right corner.

    Args:
        frame: Video frame to annotate
        frame_idx: Frame index number
        timestamp_ms: Frame timestamp in milliseconds

    Returns:
        Frame with info overlay
    """
    # Format timestamp as readable string
    # Convert ms to seconds with 3 decimal places
    timestamp_s = timestamp_ms / 1000.0

    # Prepare text lines
    text_lines = [
        f"Frame: {frame_idx}",
        f"Time: {timestamp_s:.3f}s",
        f"TS: {timestamp_ms}ms",
    ]

    # Text settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    color = (0, 255, 255)  # Yellow
    bg_color = (0, 0, 0)  # Black background
    padding = 8
    line_height = 20

    # Calculate panel dimensions
    text_widths = []
    for line in text_lines:
        (w, h), _ = cv2.getTextSize(line, font, font_scale, thickness)
        text_widths.append(w)

    panel_width = max(text_widths) + padding * 2
    panel_height = len(text_lines) * line_height + padding * 2

    # Position in top-right corner
    frame_height, frame_width = frame.shape[:2]
    panel_x = frame_width - panel_width - 10
    panel_y = 10

    # Draw semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (panel_x, panel_y),
        (panel_x + panel_width, panel_y + panel_height),
        bg_color,
        -1,
    )
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Draw border
    cv2.rectangle(
        frame,
        (panel_x, panel_y),
        (panel_x + panel_width, panel_y + panel_height),
        (100, 100, 100),
        1,
    )

    # Draw text lines
    text_y = panel_y + padding + 15
    for line in text_lines:
        cv2.putText(
            frame,
            line,
            (panel_x + padding, text_y),
            font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )
        text_y += line_height

    return frame


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

        with tqdm(total=total_frames, desc="Extracting frames", unit="frame") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Save frame
                frame_path = output_dir / frame_pattern.format(frame_idx)
                cv2.imwrite(str(frame_path), frame)

                frame_idx += 1
                pbar.update(1)

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
    output_dir: Path,
    timestamps_path: Path,
    renderer_configs: List[dict],
    *,
    frame_pattern: str = "frame_{:06d}.png",
    start_time_ms: Optional[float] = None,
    end_time_ms: Optional[float] = None,
    show_frame_info: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """
    Apply multiple data renderers to all video frames.

    Uses the simple renderer registry to load and instantiate renderers.
    Renderers are instantiated once and reused for all frames.

    Args:
        frames_dir: Directory containing extracted frames
        output_dir: Directory for rendered frames
        timestamps_path: Path to frame timestamps CSV
        renderer_configs: List of renderer configurations
            Format: [{"name": "renderer_name", "kwargs": {...}}, ...]
            - "name": Registered renderer name (e.g., "speed", "target")
            - "kwargs": Dictionary of renderer constructor arguments
        frame_pattern: Frame filename pattern
        start_time_ms: Optional start time (None=from beginning)
        end_time_ms: Optional end time (None=to end)
        show_frame_info: Show frame ID and timestamp overlay (default: True)
        progress_callback: Optional callback(count, total) for progress tracking

    Returns:
        Path to output directory

    Example:
        >>> # Using registered renderer names
        >>> renderer_configs = [
        ...     {
        ...         "name": "speed",  # Registered name
        ...         "kwargs": {
        ...             "data_path": Path("speed.jsonl"),
        ...             "position": (30, 60),
        ...             "time_offset_ms": 0
        ...         }
        ...     },
        ...     {
        ...         "name": "target",
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
        ...     end_time_ms=5000.0
        ... )
    """
    from . import get_renderer  # Import here to avoid circular dependency

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

    # Instantiate all renderers once
    logger.info(f"Preparing {len(renderer_configs)} renderers")
    renderers: List[Dict[str, Any]] = []

    for i, config in enumerate(renderer_configs):
        # Extract renderer name
        renderer_name = config.get("name")
        if not renderer_name:
            raise ValueError(
                f"Renderer config must have 'name' key: {config}"
            )

        # Get renderer class from registry
        renderer_class = get_renderer(renderer_name)
        renderer_kwargs = config.get("kwargs", {})

        # Instantiate renderer
        renderer_instance = renderer_class(**renderer_kwargs)

        renderers.append({
            "name": renderer_name,
            "instance": renderer_instance
        })

        logger.info(f"  [{i+1}] {renderer_name} -> {renderer_class.__name__}")

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
                frame = renderer_info["instance"].render(frame, timestamp_ms)

            # Draw frame info overlay (frame ID + timestamp)
            if show_frame_info:
                frame = _draw_frame_info(frame, frame_idx, timestamp_ms)

            # Save rendered frame
            output_path = output_dir / frame_pattern.format(frame_idx)
            cv2.imwrite(str(output_path), frame)

            rendered_count += 1

            # Progress reporting
            if progress_callback:
                progress_callback(rendered_count, total_frames)
            else:
                pbar.update(1)

    logger.info(f"Completed: rendered {rendered_count} frames to {output_dir}")

    return output_dir
