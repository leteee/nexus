"""
Utility functions for repro module.

Provides video metadata extraction utilities.
For time-related utilities, use time_utils module directly.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2

# Setup logger for this module
logger = logging.getLogger(__name__)


# =============================================================================
# Video Metadata Utilities
# =============================================================================


def get_video_metadata(video_path: Path) -> dict:
    """
    Extract metadata from video file.

    Args:
        video_path: Path to video file

    Returns:
        Dict with fps, total_frames, width, height, duration_s

    Example:
        >>> meta = get_video_metadata(Path("video.mp4"))
        >>> print(f"FPS: {meta['fps']}, Duration: {meta['duration_s']}s")
    """
    video_path = Path(video_path)

    logger.debug(f"Extracting metadata from video: {video_path}")

    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Failed to open video file: {video_path}")
        raise RuntimeError(f"Failed to open video: {video_path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_s = total_frames / fps if fps > 0 else 0.0

        logger.info(
            f"Video metadata: {video_path.name} - "
            f"{width}x{height}, {fps:.2f} FPS, {total_frames} frames, "
            f"{duration_s:.2f}s"
        )

        return {
            "fps": fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "duration_s": duration_s,
        }
    except Exception as e:
        logger.error(f"Error extracting video metadata from {video_path}: {e}")
        raise
    finally:
        cap.release()
        logger.debug(f"Released video capture for: {video_path}")
