"""
Time utilities for repro module.

Design goals:
- 明确的时区与单位语义（默认 Asia/Shanghai，单位默认为毫秒）。
- 支持数字/字符串/ISO8601 日期时间的解析，自动或显式单位。
- 无兼容旧 API；仅导出新的、窄接口。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, Union
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Default timezone: Asia/Shanghai
DEFAULT_TZ = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

Unit = Literal["s", "ms", "us"]
AssumeUnit = Literal["auto", "s", "ms", "us"]


def _to_datetime_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _detect_unit_from_number(value: float) -> Unit:
    """
    粗略按数量级推断：>=1e15 微秒、>=1e12 毫秒，否则秒。
    """
    if value >= 1e15:
        return "us"
    if value >= 1e12:
        return "ms"
    return "s"


def _detect_unit_from_digits(digits: int) -> Unit:
    if digits >= 15:
        return "us"
    if digits >= 13:
        return "ms"
    return "s"


def _convert_unit(value: float, from_unit: Unit, to_unit: Unit) -> float:
    # Convert via seconds
    if from_unit == "us":
        seconds = value / 1_000_000.0
    elif from_unit == "ms":
        seconds = value / 1000.0
    else:
        seconds = value

    if to_unit == "us":
        return seconds * 1_000_000.0
    if to_unit == "ms":
        return seconds * 1000.0
    return seconds


# ---------------------------------------------------------------------------
# Public parsing/formatting
# ---------------------------------------------------------------------------

def make_tz(offset_hours: Union[float, str]) -> timezone:
    """
    Create timezone from IANA name or numeric offset.
    """
    if isinstance(offset_hours, str):
        try:
            return ZoneInfo(offset_hours)
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Invalid timezone name: {offset_hours}") from exc
    return timezone(timedelta(hours=offset_hours))


def parse_timestamp(
    value: Union[str, int, float, datetime],
    *,
    target_unit: Unit = "ms",
    assume_unit: AssumeUnit = "auto",
    default_tz: Optional[ZoneInfo] = None,
) -> float:
    """
    Parse numeric / string / datetime into Unix timestamp.

    Supports:
    - datetime (aware or naive). Naive is assumed in default_tz (default Asia/Shanghai).
    - ISO8601 / date / datetime strings (datetime.fromisoformat 兼容格式)。
    - 纯数字（int/float或数字字符串），可自动推断精度（auto）或显式 assume_unit。
    """
    tz = default_tz or DEFAULT_TZ

    # datetime path
    if isinstance(value, datetime):
        aware = _to_datetime_aware(value, tz)
        return _convert_unit(aware.timestamp(), "s", target_unit)

    # numeric path
    if isinstance(value, (int, float)):
        unit = _detect_unit_from_number(float(value)) if assume_unit == "auto" else assume_unit
        return _convert_unit(float(value), unit, target_unit)

    # string path
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            numeric = float(stripped)
            digits = len(stripped.lstrip("-"))
            unit = _detect_unit_from_digits(digits) if assume_unit == "auto" else assume_unit
            return _convert_unit(numeric, unit, target_unit)

        # ISO/date/time
        try:
            dt = datetime.fromisoformat(stripped.replace(" ", "T", 1))
        except ValueError as exc:
            raise ValueError(f"Unsupported time string: '{value}'") from exc

        aware = _to_datetime_aware(dt, tz)
        return _convert_unit(aware.timestamp(), "s", target_unit)

    raise TypeError(f"Unsupported value type for timestamp parsing: {type(value)}")


def format_timestamp(
    value: Union[int, float, datetime, str],
    *,
    fmt: Literal["iso", "datetime", "date", "time"] | str = "iso",
    assume_unit: AssumeUnit = "auto",
    tz: Optional[ZoneInfo] = None,
    value_unit: Unit = "ms",
) -> str:
    """
    Format a timestamp (or datetime/ISO string) into string with desired format.
    """
    tz = tz or DEFAULT_TZ

    if isinstance(value, datetime):
        dt = _to_datetime_aware(value, tz)
    else:
        ts_ms = parse_timestamp(value, target_unit="ms", assume_unit=assume_unit, default_tz=tz)
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=tz)

    if fmt == "iso":
        return dt.isoformat()
    if fmt == "datetime":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if fmt == "date":
        return dt.strftime("%Y-%m-%d")
    if fmt == "time":
        return dt.strftime("%H:%M:%S")
    return dt.strftime(fmt)


def format_duration(duration_ms: Union[int, float]) -> str:
    """
    Human-readable duration; keeps millisecond precision for <1s.
    """
    ms = float(duration_ms)
    if ms < 1000:
        return f"{ms:.0f}ms"

    seconds_total = int(ms / 1000)
    if seconds_total < 60:
        return f"{ms/1000:.1f}s"

    minutes = seconds_total // 60
    seconds = seconds_total % 60
    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {seconds}s"


def format_timecode(timestamp_ms: Union[int, float], fps: Optional[int] = None) -> str:
    """
    Format timestamp as video timecode.
    - Default: HH:MM:SS.mmm
    - With fps: HH:MM:SS:ff (frame rounded to nearest)
    """
    total_ms = float(timestamp_ms)
    total_seconds = int(total_ms // 1000)
    ms = int(total_ms % 1000)

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if fps:
        frame = round((total_ms / 1000 - total_seconds) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame:02d}"

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


# ---------------------------------------------------------------------------
# Time provider
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeProvider:
    tz: ZoneInfo = DEFAULT_TZ

    def now(self) -> datetime:
        return datetime.now(tz=self.tz)

    def unix_ms(self) -> int:
        return int(self.now().timestamp() * 1000)

    def to_datetime(self, value: Union[str, int, float, datetime], unit: Unit = "ms") -> datetime:
        ts = parse_timestamp(value, target_unit=unit, default_tz=self.tz)
        return datetime.fromtimestamp(_convert_unit(ts, unit, "s"), tz=self.tz)

    def to_timestamp(self, value: Union[str, int, float, datetime], target_unit: Unit = "ms") -> float:
        return parse_timestamp(value, target_unit=target_unit, default_tz=self.tz)

    def format(self, value: Union[str, int, float, datetime], fmt: str = "iso", assume_unit: AssumeUnit = "auto") -> str:
        return format_timestamp(value, fmt=fmt, assume_unit=assume_unit, tz=self.tz)


__all__ = [
    "DEFAULT_TZ",
    "Unit",
    "AssumeUnit",
    "make_tz",
    "parse_timestamp",
    "format_timestamp",
    "format_duration",
    "format_timecode",
    "TimeProvider",
]
