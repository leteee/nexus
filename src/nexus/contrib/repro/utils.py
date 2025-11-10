"""
Utility functions for repro module.

Provides common utilities like time parsing, formatting and video metadata extraction.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Union

import cv2


# =============================================================================
# Time Parsing Utilities
# =============================================================================


def parse_time_value(time_value: Union[str, float, int, None]) -> Optional[int]:
    """
    Parse time value to Unix timestamp in milliseconds.

    Universal time parser that accepts multiple input formats.
    This is the main entry point for parsing time values in the repro module.

    Supported input formats:
        1. None → None (no time constraint)
        2. Integer → Direct Unix timestamp in milliseconds
        3. Float → Unix timestamp in milliseconds (converted to int)
        4. String → Parsed using parse_time_string() (see below)

    String formats (via parse_time_string):
        - ISO 8601 with timezone: "2025-10-27T08:00:00+08:00"
        - ISO 8601 UTC: "2025-10-27T00:00:00Z"
        - ISO 8601 without TZ: "2025-10-27T00:00:00" (assumes UTC)
        - Space-separated: "2025-10-27 08:00:00" (assumes UTC)
        - Date only: "2025-10-27" (assumes 00:00:00 UTC)

    Args:
        time_value: Time value in any supported format

    Returns:
        Unix timestamp in milliseconds (integer), or None if input is None

    Raises:
        ValueError: If string format is not recognized

    Examples:
        >>> # No time constraint
        >>> parse_time_value(None)
        None

        >>> # Direct Unix timestamp (most reliable)
        >>> parse_time_value(1761523200000)
        1761523200000

        >>> # Float timestamp
        >>> parse_time_value(1761523200000.123)
        1761523200000

        >>> # ISO 8601 with timezone
        >>> parse_time_value("2025-10-27T08:00:00+08:00")
        1761523200000

        >>> # Space-separated format
        >>> parse_time_value("2025-10-27 00:00:00")
        1761523200000

        >>> # Date only
        >>> parse_time_value("2025-10-27")
        1761523200000

    Best practices:
        For configuration files, prefer (in order):
        1. Direct Unix timestamp: 1761523200000 (fastest, no parsing)
        2. ISO 8601 with timezone: "2025-10-27T08:00:00+08:00" (explicit)
        3. ISO 8601 UTC: "2025-10-27T00:00:00Z" (universal)

    Note:
        Always returns INTEGER milliseconds for consistency.
        Millisecond precision is sufficient for video/sensor data.

    See also:
        parse_time_string(): Detailed string format documentation
        timestamp_to_string(): Convert timestamp back to string
    """
    if time_value is None:
        return None

    if isinstance(time_value, str):
        return parse_time_string(time_value)

    # Already a timestamp (int or float) - convert to int
    return int(time_value)


def parse_time_string(time_str: str) -> int:
    """
    Parse time string to Unix timestamp in milliseconds.

    Supported formats:
        1. ISO 8601 with timezone: "2025-10-27T08:00:00+08:00"
        2. ISO 8601 UTC: "2025-10-27T00:00:00Z"
        3. ISO 8601 without timezone: "2025-10-27T00:00:00" (assumes UTC)
        4. Space-separated datetime: "2025-10-27 08:00:00" (assumes UTC)
        5. Date only: "2025-10-27" (assumes 00:00:00 UTC)
        6. With milliseconds: "2025-10-27T00:00:00.123+08:00"
        7. With microseconds: "2025-10-27T00:00:00.123456+08:00"

    Timezone handling:
        - If timezone specified in string, it will be used for conversion
        - If no timezone specified, UTC is assumed for consistency
        - All timestamps are converted to UTC before calculating Unix timestamp

    Args:
        time_str: Time string in various formats

    Returns:
        Unix timestamp in milliseconds (integer, since 1970-01-01 00:00:00 UTC)

    Raises:
        ValueError: If time string format is not recognized

    Examples:
        >>> # ISO 8601 with explicit timezone
        >>> parse_time_string("2025-10-27T08:00:00+08:00")
        1761523200000

        >>> # Space-separated format (common in configs)
        >>> parse_time_string("2025-10-27 08:00:00")
        1761550800000

        >>> # Date only (assumes 00:00:00 UTC)
        >>> parse_time_string("2025-10-27")
        1761523200000

        >>> # UTC with Z suffix
        >>> parse_time_string("2025-10-27T00:00:00Z")
        1761523200000

    Note:
        Returns INTEGER milliseconds, following industry standards.
        For cross-machine reliability, prefer formats with explicit timezone
        or direct Unix timestamps.
    """
    time_str = time_str.strip()

    # Try parsing as ISO 8601 first (most standard)
    try:
        dt = datetime.fromisoformat(time_str)
    except ValueError:
        # Try space-separated format: "YYYY-MM-DD HH:MM:SS"
        # This is a common alternative format
        if ' ' in time_str and 'T' not in time_str:
            try:
                # Replace space with T to make it ISO 8601 compatible
                iso_str = time_str.replace(' ', 'T', 1)
                dt = datetime.fromisoformat(iso_str)
            except ValueError:
                dt = None
        else:
            dt = None

        if dt is None:
            raise ValueError(
                f"Unable to parse time string: '{time_str}'\n"
                f"Supported formats:\n"
                f"  ISO 8601 with timezone:  '2025-10-27T08:00:00+08:00'\n"
                f"  ISO 8601 UTC:            '2025-10-27T00:00:00Z'\n"
                f"  ISO 8601 (assumes UTC):  '2025-10-27T00:00:00'\n"
                f"  Space-separated:         '2025-10-27 08:00:00'\n"
                f"  Date only:               '2025-10-27'\n"
                f"\n"
                f"Or use direct Unix timestamp in milliseconds: 1761523200000"
            )

    # If naive datetime (no timezone info), assume UTC for consistency
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to Unix timestamp in milliseconds (integer)
    return int(dt.timestamp() * 1000)


# =============================================================================
# Time Formatting Utilities
# =============================================================================


def timestamp_to_datetime(
    timestamp_ms: int,
    tz: Optional[timezone] = None
) -> datetime:
    """
    Convert Unix timestamp in milliseconds to datetime object.

    Args:
        timestamp_ms: Unix timestamp in milliseconds (integer)
        tz: Target timezone (default: UTC)

    Returns:
        datetime object in specified timezone

    Examples:
        >>> # Convert to UTC datetime
        >>> dt = timestamp_to_datetime(1761523200000)
        >>> print(dt)
        2025-10-27 00:00:00+00:00

        >>> # Convert to Beijing time (UTC+8)
        >>> from datetime import timezone, timedelta
        >>> beijing_tz = timezone(timedelta(hours=8))
        >>> dt = timestamp_to_datetime(1761523200000, tz=beijing_tz)
        >>> print(dt)
        2025-10-27 08:00:00+08:00
    """
    if tz is None:
        tz = timezone.utc

    # Convert milliseconds to seconds
    timestamp_s = timestamp_ms / 1000.0

    # Create datetime in UTC first
    dt_utc = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)

    # Convert to target timezone
    return dt_utc.astimezone(tz)


def timestamp_to_string(
    timestamp_ms: int,
    fmt: str = "iso",
    tz: Optional[timezone] = None
) -> str:
    """
    Convert Unix timestamp in milliseconds to formatted string.

    Args:
        timestamp_ms: Unix timestamp in milliseconds (integer)
        fmt: Output format - "iso" (default), "datetime", "date", "time", or custom strftime format
        tz: Target timezone (default: UTC)

    Returns:
        Formatted time string

    Examples:
        >>> # ISO 8601 format (default)
        >>> timestamp_to_string(1761523200000)
        '2025-10-27T00:00:00+00:00'

        >>> # ISO 8601 with Beijing timezone
        >>> from datetime import timezone, timedelta
        >>> beijing_tz = timezone(timedelta(hours=8))
        >>> timestamp_to_string(1761523200000, tz=beijing_tz)
        '2025-10-27T08:00:00+08:00'

        >>> # Human-readable datetime
        >>> timestamp_to_string(1761523200000, fmt="datetime")
        '2025-10-27 00:00:00'

        >>> # Date only
        >>> timestamp_to_string(1761523200000, fmt="date")
        '2025-10-27'

        >>> # Time only
        >>> timestamp_to_string(1761523200000, fmt="time")
        '00:00:00'

        >>> # Custom format
        >>> timestamp_to_string(1761523200000, fmt="%Y年%m月%d日 %H:%M:%S")
        '2025年10月27日 00:00:00'
    """
    dt = timestamp_to_datetime(timestamp_ms, tz=tz)

    if fmt == "iso":
        return dt.isoformat()
    elif fmt == "datetime":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    elif fmt == "date":
        return dt.strftime("%Y-%m-%d")
    elif fmt == "time":
        return dt.strftime("%H:%M:%S")
    else:
        # Custom strftime format
        return dt.strftime(fmt)


def format_duration_ms(duration_ms: int) -> str:
    """
    Format duration in milliseconds to human-readable string.

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        Formatted duration string (e.g., "1h 23m 45s", "45.5s", "123ms")

    Examples:
        >>> format_duration_ms(5000)
        '5.0s'

        >>> format_duration_ms(125000)
        '2m 5s'

        >>> format_duration_ms(5023456)
        '1h 23m 43s'

        >>> format_duration_ms(500)
        '500ms'
    """
    if duration_ms < 1000:
        return f"{duration_ms}ms"

    seconds = duration_ms / 1000.0

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours = minutes // 60
    minutes = minutes % 60

    return f"{hours}h {minutes}m {seconds}s"


def get_current_timestamp_ms() -> int:
    """
    Get current Unix timestamp in milliseconds.

    Returns:
        Current Unix timestamp in milliseconds (integer)

    Example:
        >>> now = get_current_timestamp_ms()
        >>> print(f"Current time: {timestamp_to_string(now)}")
    """
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def create_timezone(offset_hours: float) -> timezone:
    """
    Create timezone from UTC offset in hours.

    Args:
        offset_hours: UTC offset in hours (e.g., 8 for UTC+8, -5 for UTC-5)

    Returns:
        timezone object

    Examples:
        >>> # Beijing time (UTC+8)
        >>> beijing_tz = create_timezone(8)
        >>> print(beijing_tz)
        UTC+08:00

        >>> # New York time (UTC-5)
        >>> ny_tz = create_timezone(-5)
        >>> print(ny_tz)
        UTC-05:00
    """
    return timezone(timedelta(hours=offset_hours))


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
