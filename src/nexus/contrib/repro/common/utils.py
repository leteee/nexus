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


def parse_time_value(
    time_value: Union[str, float, int, None], unit: str = "ms"
) -> Optional[float]:
    """
    Parse time value to a Unix timestamp in a specified unit, preserving precision.

    This is the main entry point for parsing time values in the repro module.
    It works by converting all inputs to a high-precision millisecond timestamp
    internally, and then converting to the desired output unit if needed.

    It automatically detects the unit of numeric timestamps based on context:
    - For `int` or `float` types, unit is inferred from the number's magnitude.
    - For numeric `str` types, unit is inferred from the string's length.

    Supported input formats:
        1. None → None (no time constraint)
        2. Integer/Float → Parsed based on magnitude:
           - >= 1e14: assumed to be microseconds (us)
           - >= 1e11: assumed to be milliseconds (ms)
           - < 1e11: assumed to be seconds (s)
        3. Numeric String → Parsed based on digit length:
           - >= 15 digits: assumed to be microseconds (us)
           - 12-14 digits: assumed to be milliseconds (ms)
           - < 12 digits: assumed to be seconds (s)
        4. Date/Time String → Parsed with millisecond precision.

    Args:
        time_value: Time value in any supported format.
        unit: The unit of the output timestamp. "us" (microseconds), "ms"
            (milliseconds), or "s" (seconds). Defaults to "ms".

    Returns:
        Unix timestamp in the specified unit (float), or None if input is None.

    Raises:
        ValueError: If string format is not recognized or unit is unsupported.
        TypeError: If the input type is not supported.
    """
    if time_value is None:
        logger.debug("Time value is None, returning None")
        return None

    timestamp_ms: float

    if isinstance(time_value, (int, float)):
        # For int/float, use magnitude to infer unit to preserve float precision
        numeric_value = float(time_value)
        # Thresholds are set between typical s/ms (1e11) and ms/us (1e14) ranges
        if numeric_value >= 1e14:  # Likely microseconds or higher precision
            logger.debug(f"Parsing numeric value as us: {numeric_value}")
            timestamp_ms = numeric_value / 1000
        elif numeric_value >= 1e11:  # Likely milliseconds
            logger.debug(f"Parsing numeric value as ms: {numeric_value}")
            timestamp_ms = numeric_value
        else:  # Likely seconds
            logger.debug(f"Parsing numeric value as s: {numeric_value}")
            timestamp_ms = numeric_value * 1000

    elif isinstance(time_value, str):
        time_str = time_value.strip()
        if time_str.isdigit():
            # For integer strings, use digit count to infer unit
            numeric_value = int(time_str)
            num_digits = len(time_str)
            if num_digits >= 15:  # Assume microseconds
                logger.debug(f"Parsing numeric string as us: '{time_str}'")
                timestamp_ms = numeric_value / 1000
            elif num_digits >= 12:  # Assume milliseconds
                logger.debug(f"Parsing numeric string as ms: '{time_str}'")
                timestamp_ms = float(numeric_value)
            else:  # Assume seconds
                logger.debug(f"Parsing numeric string as s: '{time_str}'")
                timestamp_ms = float(numeric_value * 1000)
        else:
            # For date/time strings, parse with high precision
            logger.debug(f"Parsing date/time string: '{time_str}'")
            timestamp_ms = parse_time_string(time_str)
    else:
        raise TypeError(f"Unsupported input type for time_value: {type(time_value)}")

    # Convert from unified millisecond float to the desired output unit
    if unit == "us":
        return timestamp_ms * 1000
    elif unit == "ms":
        return timestamp_ms
    elif unit == "s":
        return timestamp_ms / 1000
    else:
        raise ValueError(
            f"Unsupported time unit: '{unit}'. Supported units are 'us', 'ms', 's'."
        )


def parse_time_string(time_str: str) -> float:
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
        Unix timestamp in milliseconds (float, since 1970-01-01 00:00:00 UTC)

    Raises:
        ValueError: If time string format is not recognized
    """
    time_str = time_str.strip()

    # Try parsing as ISO 8601 first (most standard)
    try:
        dt = datetime.fromisoformat(time_str)
    except ValueError:
        # Try space-separated format: "YYYY-MM-DD HH:MM:SS"
        # This is a common alternative format
        if " " in time_str and "T" not in time_str:
            try:
                # Replace space with T to make it ISO 8601 compatible
                iso_str = time_str.replace(" ", "T", 1)
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

    # Convert to Unix timestamp in milliseconds (float)
    timestamp_ms = dt.timestamp() * 1000
    logger.debug(f"Converted '{time_str}' to timestamp: {timestamp_ms} ms")

    return timestamp_ms


# =============================================================================
# Time Formatting Utilities
# =============================================================================


def timestamp_to_datetime(
    timestamp_ms: float,
    tz: Optional[timezone] = None
) -> datetime:
    """
    Convert Unix timestamp in milliseconds to datetime object.

    Args:
        timestamp_ms: Unix timestamp in milliseconds (float or int)
        tz: Target timezone (default: UTC+8 / Beijing Time)

    Returns:
        datetime object in specified timezone

    Examples:
        >>> # Convert to Beijing time (UTC+8, default)
        >>> dt = timestamp_to_datetime(1761523200000.0)
        >>> print(dt)
        2025-10-27 08:00:00+08:00

        >>> # Convert to UTC explicitly
        >>> from datetime import timezone
        >>> dt = timestamp_to_datetime(1761523200000.0, tz=timezone.utc)
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
    timestamp_ms: float,
    fmt: str = "iso",
    tz: Optional[timezone] = None
) -> str:
    """
    Convert Unix timestamp in milliseconds to formatted string.

    Args:
        timestamp_ms: Unix timestamp in milliseconds (float or int)
        fmt: Output format - "iso" (default), "datetime", "date", "time", or custom strftime format
        tz: Target timezone (default: UTC+8 / Beijing Time)

    Returns:
        Formatted time string

    Examples:
        >>> # ISO 8601 format with Beijing time (default)
        >>> timestamp_to_string(1761523200000.0)
        '2025-10-27T08:00:00+08:00'

        >>> # ISO 8601 with UTC
        >>> from datetime import timezone
        >>> timestamp_to_string(1761523200000.0, tz=timezone.utc)
        '2025-10-27T00:00:00+00:00'

        >>> # Human-readable datetime (Beijing time)
        >>> timestamp_to_string(1761523200000.0, fmt="datetime")
        '2025-10-27 08:00:00'

        >>> # Date only
        >>> timestamp_to_string(1761523200000.0, fmt="date")
        '2025-10-27'

        >>> # Time only
        >>> timestamp_to_string(1761523200000.0, fmt="time")
        '08:00:00'

        >>> # Custom format
        >>> timestamp_to_string(1761523200000.0, fmt="%Y年%m月%d日 %H:%M:%S")
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


def format_duration_ms(duration_ms: float) -> str:
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


def get_current_timestamp_ms() -> float:
    """
    Get current Unix timestamp in milliseconds.

    Returns:
        Current Unix timestamp in milliseconds (float)

    Example:
        >>> now = get_current_timestamp_ms()
        >>> print(f"Current time: {timestamp_to_string(now)}")
    """
    timestamp_ms = datetime.now(tz=timezone.utc).timestamp() * 1000
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
