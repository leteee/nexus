"""
Utility functions for repro module.

Provides common utilities like time parsing, formatting and video metadata extraction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Union

import cv2

# Setup logger for this module
logger = logging.getLogger(__name__)


# =============================================================================
# Default Timezone Configuration
# =============================================================================

# Default timezone: UTC+8 (China Standard Time / Beijing Time)
DEFAULT_TIMEZONE = timezone(timedelta(hours=8))


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
        - ISO 8601 without TZ: "2025-10-27T00:00:00" (assumes UTC+8)
        - Space-separated: "2025-10-27 08:00:00" (assumes UTC+8)
        - Date only: "2025-10-27" (assumes 00:00:00 UTC+8)

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

        >>> # Space-separated format (assumes UTC+8 by default)
        >>> parse_time_value("2025-10-27 08:00:00")
        1761523200000

        >>> # Date only (assumes 00:00:00 UTC+8)
        >>> parse_time_value("2025-10-27")
        1761523200000

    Best practices:
        For configuration files, prefer (in order):
        1. Direct Unix timestamp: 1761523200000 (fastest, no parsing)
        2. ISO 8601 with timezone: "2025-10-27T08:00:00+08:00" (explicit)
        3. Space-separated with TZ: "2025-10-27 08:00:00" (defaults to UTC+8)

    Note:
        Always returns INTEGER milliseconds for consistency.
        Millisecond precision is sufficient for video/sensor data.
        Default timezone is UTC+8 (Beijing Time) when not specified.

    See also:
        parse_time_string(): Detailed string format documentation
        timestamp_to_string(): Convert timestamp back to string
    """
    if time_value is None:
        logger.debug("Time value is None, returning None")
        return None

    if isinstance(time_value, str):
        logger.debug(f"Parsing time string: '{time_value}'")
        return parse_time_string(time_value)

    # Already a timestamp (int or float) - convert to int
    timestamp_ms = int(time_value)
    logger.debug(f"Using direct timestamp: {timestamp_ms} ms")
    return timestamp_ms


def parse_time_string(time_str: str) -> int:
    """
    Parse time string to Unix timestamp in milliseconds.

    Supported formats:
        1. ISO 8601 with timezone: "2025-10-27T08:00:00+08:00"
        2. ISO 8601 UTC: "2025-10-27T00:00:00Z"
        3. ISO 8601 without timezone: "2025-10-27T00:00:00" (assumes UTC+8)
        4. Space-separated datetime: "2025-10-27 08:00:00" (assumes UTC+8)
        5. Date only: "2025-10-27" (assumes 00:00:00 UTC+8)
        6. With milliseconds: "2025-10-27T00:00:00.123+08:00"
        7. With microseconds: "2025-10-27T00:00:00.123456+08:00"

    Timezone handling:
        - If timezone specified in string, it will be used for conversion
        - If no timezone specified, UTC+8 (Beijing Time) is assumed as default
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

        >>> # Space-separated format (common in configs, assumes UTC+8)
        >>> parse_time_string("2025-10-27 08:00:00")
        1761523200000

        >>> # Date only (assumes 00:00:00 UTC+8)
        >>> parse_time_string("2025-10-27")
        1761523200000

        >>> # UTC with Z suffix (explicit UTC)
        >>> parse_time_string("2025-10-27T00:00:00Z")
        1761494400000

    Note:
        Returns INTEGER milliseconds, following industry standards.
        When no timezone is specified, UTC+8 (Beijing Time) is used as default.
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
            logger.error(f"Failed to parse time string: '{time_str}'")
            raise ValueError(
                f"Unable to parse time string: '{time_str}'\n"
                f"Supported formats:\n"
                f"  ISO 8601 with timezone:  '2025-10-27T08:00:00+08:00'\n"
                f"  ISO 8601 UTC:            '2025-10-27T00:00:00Z'\n"
                f"  ISO 8601 (assumes UTC+8): '2025-10-27T00:00:00'\n"
                f"  Space-separated:         '2025-10-27 08:00:00' (assumes UTC+8)\n"
                f"  Date only:               '2025-10-27' (assumes UTC+8)\n"
                f"\n"
                f"Or use direct Unix timestamp in milliseconds: 1761523200000"
            )

    # If naive datetime (no timezone info), assume UTC+8 (Beijing Time) as default
    if dt.tzinfo is None:
        logger.debug(
            f"Time string '{time_str}' has no timezone info, "
            f"assuming default timezone UTC+8 (Beijing Time)"
        )
        dt = dt.replace(tzinfo=DEFAULT_TIMEZONE)
    else:
        logger.debug(f"Parsed time string '{time_str}' with timezone: {dt.tzinfo}")

    # Convert to Unix timestamp in milliseconds (integer)
    timestamp_ms = int(dt.timestamp() * 1000)
    logger.debug(f"Converted '{time_str}' to timestamp: {timestamp_ms} ms")

    return timestamp_ms


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
        tz: Target timezone (default: UTC+8 / Beijing Time)

    Returns:
        datetime object in specified timezone

    Examples:
        >>> # Convert to Beijing time (UTC+8, default)
        >>> dt = timestamp_to_datetime(1761523200000)
        >>> print(dt)
        2025-10-27 08:00:00+08:00

        >>> # Convert to UTC explicitly
        >>> from datetime import timezone
        >>> dt = timestamp_to_datetime(1761523200000, tz=timezone.utc)
        >>> print(dt)
        2025-10-27 00:00:00+00:00
    """
    if tz is None:
        tz = DEFAULT_TIMEZONE

    # Convert milliseconds to seconds
    timestamp_s = timestamp_ms / 1000.0

    # Create datetime in UTC first
    dt_utc = datetime.fromtimestamp(timestamp_s, tz=timezone.utc)

    # Convert to target timezone
    dt = dt_utc.astimezone(tz)

    logger.debug(
        f"Converted timestamp {timestamp_ms} ms to datetime: {dt.isoformat()} "
        f"(timezone: {tz})"
    )

    return dt


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
        tz: Target timezone (default: UTC+8 / Beijing Time)

    Returns:
        Formatted time string

    Examples:
        >>> # ISO 8601 format with Beijing time (default)
        >>> timestamp_to_string(1761523200000)
        '2025-10-27T08:00:00+08:00'

        >>> # ISO 8601 with UTC
        >>> from datetime import timezone
        >>> timestamp_to_string(1761523200000, tz=timezone.utc)
        '2025-10-27T00:00:00+00:00'

        >>> # Human-readable datetime (Beijing time)
        >>> timestamp_to_string(1761523200000, fmt="datetime")
        '2025-10-27 08:00:00'

        >>> # Date only
        >>> timestamp_to_string(1761523200000, fmt="date")
        '2025-10-27'

        >>> # Time only
        >>> timestamp_to_string(1761523200000, fmt="time")
        '08:00:00'

        >>> # Custom format
        >>> timestamp_to_string(1761523200000, fmt="%Y年%m月%d日 %H:%M:%S")
        '2025年10月27日 08:00:00'
    """
    dt = timestamp_to_datetime(timestamp_ms, tz=tz)

    if fmt == "iso":
        result = dt.isoformat()
    elif fmt == "datetime":
        result = dt.strftime("%Y-%m-%d %H:%M:%S")
    elif fmt == "date":
        result = dt.strftime("%Y-%m-%d")
    elif fmt == "time":
        result = dt.strftime("%H:%M:%S")
    else:
        # Custom strftime format
        result = dt.strftime(fmt)

    logger.debug(f"Formatted timestamp {timestamp_ms} ms as '{result}' (format: {fmt})")

    return result


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
    timestamp_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    logger.debug(f"Current timestamp: {timestamp_ms} ms")
    return timestamp_ms


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
    tz = timezone(timedelta(hours=offset_hours))
    logger.debug(f"Created timezone with offset: UTC{offset_hours:+.1f}")
    return tz


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
