"""
Time utilities for repro module.

Provides time parsing, formatting, and timezone handling with UTC+8 as default timezone.
All timestamps are in milliseconds for consistency.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Default timezone: UTC+8 (China Standard Time / Beijing Time)
DEFAULT_TIMEZONE = timezone(timedelta(hours=8))


# =============================================================================
# Time Parsing
# =============================================================================


def parse_time_value(
    time_value: Union[str, float, int, None],
    unit: str = "ms"
) -> Optional[float]:
    """
    Parse time value to Unix timestamp in specified unit.

    Automatically detects input format and converts to target unit with precision.

    Supported input formats:
        1. None → None (no time constraint)
        2. Integer/Float → Inferred by magnitude:
           - >= 1e14: microseconds (us)
           - >= 1e11: milliseconds (ms)
           - < 1e11: seconds (s)
        3. Numeric String → Inferred by digit length:
           - >= 15 digits: microseconds (us)
           - 12-14 digits: milliseconds (ms)
           - < 12 digits: seconds (s)
        4. Date/Time String → Parsed with millisecond precision

    Args:
        time_value: Time value in any supported format
        unit: Output unit - "us" (microseconds), "ms" (milliseconds), or "s" (seconds)

    Returns:
        Unix timestamp in specified unit (float), or None if input is None

    Raises:
        ValueError: If string format is not recognized or unit is unsupported
        TypeError: If input type is not supported

    Examples:
        >>> parse_time_value("2025-10-27 08:00:00")
        1730001600000.0

        >>> parse_time_value(1730001600000)
        1730001600000.0

        >>> parse_time_value(1730001600, unit="s")
        1730001600.0
    """
    if time_value is None:
        logger.debug("Time value is None, returning None")
        return None

    timestamp_ms: float

    if isinstance(time_value, (int, float)):
        # Infer unit from magnitude
        numeric_value = float(time_value)
        if numeric_value >= 1e14:  # Microseconds
            logger.debug(f"Parsing numeric value as us: {numeric_value}")
            timestamp_ms = numeric_value / 1000
        elif numeric_value >= 1e11:  # Milliseconds
            logger.debug(f"Parsing numeric value as ms: {numeric_value}")
            timestamp_ms = numeric_value
        else:  # Seconds
            logger.debug(f"Parsing numeric value as s: {numeric_value}")
            timestamp_ms = numeric_value * 1000

    elif isinstance(time_value, str):
        time_str = time_value.strip()
        if time_str.isdigit():
            # Infer unit from digit count
            numeric_value = int(time_str)
            num_digits = len(time_str)
            if num_digits >= 15:  # Microseconds
                logger.debug(f"Parsing numeric string as us: '{time_str}'")
                timestamp_ms = numeric_value / 1000
            elif num_digits >= 12:  # Milliseconds
                logger.debug(f"Parsing numeric string as ms: '{time_str}'")
                timestamp_ms = float(numeric_value)
            else:  # Seconds
                logger.debug(f"Parsing numeric string as s: '{time_str}'")
                timestamp_ms = float(numeric_value * 1000)
        else:
            # Parse as date/time string
            logger.debug(f"Parsing date/time string: '{time_str}'")
            timestamp_ms = parse_time_string(time_str)
    else:
        raise TypeError(f"Unsupported input type for time_value: {type(time_value)}")

    # Convert to target unit
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


def parse_time_string(
    time_str: str,
    default_tz: Optional[timezone] = None
) -> float:
    """
    Parse time string to Unix timestamp in milliseconds.

    Supported formats:
        - ISO 8601 with timezone: "2025-10-27T08:00:00+08:00"
        - ISO 8601 UTC: "2025-10-27T00:00:00Z"
        - ISO 8601 without timezone: "2025-10-27T00:00:00" (assumes default_tz)
        - Space-separated: "2025-10-27 08:00:00" (assumes default_tz)
        - Date only: "2025-10-27" (assumes 00:00:00 in default_tz)
        - With milliseconds: "2025-10-27T00:00:00.123+08:00"
        - With microseconds: "2025-10-27T00:00:00.123456+08:00"

    Args:
        time_str: Time string in various formats
        default_tz: Default timezone if not specified in string (default: UTC+8)

    Returns:
        Unix timestamp in milliseconds (float)

    Raises:
        ValueError: If time string format is not recognized

    Examples:
        >>> parse_time_string("2025-10-27 08:00:00")
        1730001600000.0

        >>> parse_time_string("2025-10-27T08:00:00+08:00")
        1730001600000.0
    """
    if default_tz is None:
        default_tz = DEFAULT_TIMEZONE

    time_str = time_str.strip()

    # Try parsing as ISO 8601
    try:
        dt = datetime.fromisoformat(time_str)
    except ValueError:
        # Try space-separated format
        if " " in time_str and "T" not in time_str:
            try:
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
                f"  ISO 8601 (assumes {default_tz}): '2025-10-27T00:00:00'\n"
                f"  Space-separated:         '2025-10-27 08:00:00'\n"
                f"  Date only:               '2025-10-27'\n"
                f"\n"
                f"Or use direct Unix timestamp in milliseconds"
            )

    # Apply default timezone if naive datetime
    if dt.tzinfo is None:
        logger.debug(
            f"Time string '{time_str}' has no timezone, "
            f"assuming default timezone {default_tz}"
        )
        dt = dt.replace(tzinfo=default_tz)
    else:
        logger.debug(f"Parsed time string '{time_str}' with timezone: {dt.tzinfo}")

    # Convert to Unix timestamp in milliseconds
    timestamp_ms = dt.timestamp() * 1000
    logger.debug(f"Converted '{time_str}' to timestamp: {timestamp_ms} ms")

    return timestamp_ms


# =============================================================================
# Time Formatting
# =============================================================================


def timestamp_to_datetime(
    timestamp_ms: float,
    tz: Optional[timezone] = None
) -> datetime:
    """
    Convert Unix timestamp in milliseconds to datetime object.

    Args:
        timestamp_ms: Unix timestamp in milliseconds
        tz: Target timezone (default: UTC+8)

    Returns:
        datetime object in specified timezone

    Examples:
        >>> dt = timestamp_to_datetime(1730001600000.0)
        >>> print(dt)
        2025-10-27 08:00:00+08:00
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
        timestamp_ms: Unix timestamp in milliseconds
        fmt: Output format - "iso", "datetime", "date", "time", or custom strftime format
        tz: Target timezone (default: UTC+8)

    Returns:
        Formatted time string

    Examples:
        >>> timestamp_to_string(1730001600000.0)
        '2025-10-27T08:00:00+08:00'

        >>> timestamp_to_string(1730001600000.0, fmt="datetime")
        '2025-10-27 08:00:00'

        >>> timestamp_to_string(1730001600000.0, fmt="%Y年%m月%d日")
        '2025年10月27日'
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
        Formatted duration string (e.g., "1h 23m 45s", "5.0s", "123ms")

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
        return f"{duration_ms:.0f}ms"

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


# =============================================================================
# Utility Functions
# =============================================================================


def get_current_timestamp_ms() -> float:
    """
    Get current Unix timestamp in milliseconds.

    Returns:
        Current Unix timestamp in milliseconds (float)

    Example:
        >>> now = get_current_timestamp_ms()
        >>> print(f"Current time: {now}")
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
        >>> beijing_tz = create_timezone(8)
        >>> print(beijing_tz)
        UTC+08:00

        >>> ny_tz = create_timezone(-5)
        >>> print(ny_tz)
        UTC-05:00
    """
    tz = timezone(timedelta(hours=offset_hours))
    logger.debug(f"Created timezone with offset: UTC{offset_hours:+.1f}")
    return tz


def format_timecode(timestamp_ms: float) -> str:
    """
    Format timestamp as video timecode (HH:MM:SS.mmm).
    
    Args:
        timestamp_ms: Timestamp in milliseconds
        
    Returns:
        Formatted timecode string (e.g. "01:23:45.678")
    """
    total_seconds = int(timestamp_ms / 1000)
    ms = int(timestamp_ms % 1000)
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
