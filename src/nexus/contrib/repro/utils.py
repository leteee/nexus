"""
Utility functions for repro module.

Provides common utilities like time parsing, formatting and video metadata extraction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np

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
                f