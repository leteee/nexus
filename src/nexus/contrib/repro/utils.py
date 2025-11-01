"""
Utility functions for repro module.

Provides common utilities like time parsing and video metadata extraction.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2


# =============================================================================
# Time Parsing Utilities
# =============================================================================


def parse_time_value(time_value: str | float | None) -> float | None:
    """
    Parse time value to Unix timestamp in milliseconds.

    Supports multiple input formats:
    - None: Returns None (no time constraint)
    - str: Time string like "2025-10-27 00:00:00"
    - float/int: Direct millisecond timestamp

    Args:
        time_value: Time value in various formats

    Returns:
        Unix timestamp in milliseconds, or None

    Example:
        >>> parse_time_value(None)
        None
        >>> parse_time_value("2025-10-27 00:00:00")
        1759284000000.0
        >>> parse_time_value(1759284000000.0)
        1759284000000.0
    """
    if time_value is None:
        return None

    if isinstance(time_value, str):
        return parse_time_string(time_value)

    # Assume it's already a timestamp
    return float(time_value)


def parse_time_string(time_str: str) -> float:
    """
    Parse time string to Unix timestamp in milliseconds.

    Supports formats:
    - "2025-10-27 00:00:00"
    - "2025-10-27T00:00:00"
    - ISO 8601 with timezone

    Args:
        time_str: Time string in standard format

    Returns:
        Unix timestamp in milliseconds

    Example:
        >>> parse_time_string("2025-10-27 00:00:00")
        1759284000000.0
    """
    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.timestamp() * 1000.0
        except ValueError:
            continue

    # Try parsing with ISO format
    try:
        dt = datetime.fromisoformat(time_str)
        return dt.timestamp() * 1000.0
    except ValueError:
        raise ValueError(
            f"Unable to parse time string: {time_str}. "
            f"Expected format: 'YYYY-MM-DD HH:MM:SS'"
        )


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
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_s = total_frames / fps if fps > 0 else 0.0

        return {
            "fps": fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "duration_s": duration_s,
        }
    finally:
        cap.release()
