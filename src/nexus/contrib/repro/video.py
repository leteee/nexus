"""
Video processing utilities for frame extraction and composition.

Provides functions to split videos into frames and compose frames back into video.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pandas as pd

from .types import VideoMetadata

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: Path,
    output_dir: Path,
    *,
    frame_pattern: str = "frame_{:06d}.png",
    save_timestamps: bool = True,
) -> VideoMetadata:
    """
    Extract all frames from video and save as images.

    Args:
        video_path: Path to input video file
        output_dir: Directory to save extracted frames
        frame_pattern: Filename pattern for frames (must contain one format spec)
        save_timestamps: Whether to save frame_timestamps.csv

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

        frame_timestamps = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Save frame
            frame_path = output_dir / frame_pattern.format(frame_idx)
            cv2.imwrite(str(frame_path), frame)

            # Calculate timestamp (ms)
            timestamp_ms = (frame_idx / fps) * 1000.0
            frame_timestamps.append(
                {"frame_index": frame_idx, "timestamp_ms": timestamp_ms}
            )

            if (frame_idx + 1) % 100 == 0:
                logger.info(f"Extracted {frame_idx + 1} frames...")

            frame_idx += 1

        logger.info(f"Completed: extracted {frame_idx} frames to {output_dir}")

        # Save timestamp mapping
        if save_timestamps:
            timestamps_df = pd.DataFrame(frame_timestamps)
            csv_path = output_dir / "frame_timestamps.csv"
            timestamps_df.to_csv(csv_path, index=False)
            logger.info(f"Saved frame timestamps to {csv_path}")

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


def get_frame_at_timestamp(
    frames_dir: Path,
    timestamp_ms: float,
    frame_timestamps: pd.DataFrame,
    *,
    frame_pattern: str = "frame_{:06d}.png",
) -> Optional[np.ndarray]:
    """
    Load the frame corresponding to a specific timestamp.

    Args:
        frames_dir: Directory containing frame images
        timestamp_ms: Target timestamp in milliseconds
        frame_timestamps: DataFrame mapping frame_index to timestamp_ms
        frame_pattern: Filename pattern for frames

    Returns:
        Frame as numpy array, or None if not found
    """
    # Find closest frame
    idx = (frame_timestamps["timestamp_ms"] - timestamp_ms).abs().idxmin()
    frame_index = frame_timestamps.loc[idx, "frame_index"]

    frame_path = frames_dir / frame_pattern.format(int(frame_index))
    if not frame_path.exists():
        logger.warning(f"Frame not found: {frame_path}")
        return None

    frame = cv2.imread(str(frame_path))
    return frame
