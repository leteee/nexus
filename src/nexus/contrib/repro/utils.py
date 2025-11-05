"""
Utility functions for repro module.

Provides common utilities like time parsing and video metadata extraction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import cv2


# =============================================================================
# Time Parsing Utilities
# =============================================================================


def parse_time_value(time_value: Union[str, float, int, None]) -> Optional[int]:
    """
    Parse time value to Unix timestamp in milliseconds.

    This is the main entry point for parsing time values in the repro module.
    Internally, all times are represented as Unix timestamps in milliseconds (INTEGER).

    Supported input formats:
        1. None: Returns None (no time constraint)
        2. Number (int/float): Direct Unix timestamp in milliseconds
        3. String: ISO 8601 formatted time string (see parse_time_string)

    Args:
        time_value: Time value in various formats

    Returns:
        Unix timestamp in milliseconds (integer), or None if input is None

    Examples:
        >>> # No time constraint
        >>> parse_time_value(None)
        None

        >>> # Direct Unix timestamp (most reliable, no parsing)
        >>> parse_time_value(1761523200000)
        1761523200000

        >>> # ISO 8601 with timezone (recommended for strings)
        >>> parse_time_value("2025-10-27T08:00:00+08:00")
        1761523200000

        >>> # ISO 8601 UTC
        >>> parse_time_value("2025-10-27T00:00:00Z")
        1761523200000

        >>> # ISO 8601 without timezone (assumes UTC)
        >>> parse_time_value("2025-10-27T00:00:00")
        1761523200000

    Best practices:
        For configuration files, prefer:
        1. Direct Unix timestamp: 1761523200000 (most reliable, no parsing)
        2. ISO 8601 with timezone: "2025-10-27T08:00:00+08:00" (clear intent)
        3. ISO 8601 UTC: "2025-10-27T00:00:00Z" (universal time)

    Note:
        Returns INTEGER milliseconds, following industry standards (JavaScript,
        Java, databases). Millisecond precision is sufficient for video/sensor data.

    See also:
        parse_time_string(): For string parsing details
    """
    if time_value is None:
        return None

    if isinstance(time_value, str):
        return parse_time_string(time_value)

    # Already a timestamp (int or float) - convert to int
    return int(time_value)


def parse_time_string(time_str: str) -> int:
    """
    Parse ISO 8601 time string to Unix timestamp in milliseconds.

    Supported formats (ISO 8601 only):
        - With timezone: "2025-10-27T08:00:00+08:00"
        - UTC (Z suffix): "2025-10-27T00:00:00Z"
        - Without timezone: "2025-10-27T00:00:00" (assumes UTC)
        - With milliseconds: "2025-10-27T00:00:00.000+08:00"
        - With microseconds: "2025-10-27T00:00:00.000000+08:00"

    Timezone handling:
        - If timezone is specified in the string, it will be used for conversion
        - If no timezone is specified, UTC is assumed for cross-machine consistency
        - All timestamps are converted to UTC before calculating Unix timestamp

    Args:
        time_str: ISO 8601 formatted time string

    Returns:
        Unix timestamp in milliseconds (integer, since 1970-01-01 00:00:00 UTC)

    Raises:
        ValueError: If time string format is not recognized

    Examples:
        >>> # With explicit timezone
        >>> parse_time_string("2025-10-27T08:00:00+08:00")
        1761523200000  # Beijing time converted to UTC

        >>> # UTC with Z suffix
        >>> parse_time_string("2025-10-27T00:00:00Z")
        1761523200000

        >>> # Without timezone (assumes UTC)
        >>> parse_time_string("2025-10-27T00:00:00")
        1761523200000

    Note:
        Returns INTEGER milliseconds, following industry standards (JavaScript,
        Java, databases). For cross-machine reliability, prefer using formats
        with explicit timezone or direct Unix timestamps.
    """
    # Try parsing as ISO 8601 (supports timezone-aware formats)
    try:
        dt = datetime.fromisoformat(time_str)
    except ValueError:
        raise ValueError(
            f"Unable to parse time string: '{time_str}'. "
            f"Expected ISO 8601 format: 'YYYY-MM-DDTHH:MM:SS' with optional timezone.\n"
            f"Examples:\n"
            f"  - With timezone: '2025-10-27T08:00:00+08:00'\n"
            f"  - UTC: '2025-10-27T00:00:00Z'\n"
            f"  - Assume UTC: '2025-10-27T00:00:00'\n"
            f"Or use direct Unix timestamp in milliseconds: 1761523200000"
        )

    # If naive datetime (no timezone info), assume UTC for consistency
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to Unix timestamp in milliseconds (integer)
    return int(dt.timestamp() * 1000)


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
