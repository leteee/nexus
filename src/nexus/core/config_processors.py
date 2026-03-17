"""
Business configuration processing pipeline.

Responsibilities:
- Reference resolution (using existing ConfigResolver) on `defaults` namespace.
- Path normalization for annotated path fields.
- Time normalization for annotated time fields.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from .config_resolver import ConfigResolver


DEFAULT_TIMEZONE = ZoneInfo("Asia/Shanghai")


# Annotation markers ----------------------------------------------------------

class PathField:
    def __init__(self, base: str = "case") -> None:
        self.base = base  # "case" or "project"


class TimeField:
    def __init__(self, unit: str = "ms") -> None:
        self.unit = unit


# Helpers --------------------------------------------------------------------

def _is_path_field(meta: Any) -> bool:
    return isinstance(meta, PathField)


def _is_time_field(meta: Any) -> bool:
    return isinstance(meta, TimeField)


# Processing pipeline --------------------------------------------------------

@dataclass
class ProcessingContext:
    project_root: Path
    case_root: Path
    timezone: ZoneInfo = DEFAULT_TIMEZONE


class ReferenceProcessor:
    def __init__(self, defaults: Dict[str, Any]):
        self.resolver = ConfigResolver(defaults)

    def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.resolver.resolve(data)


class PathProcessor:
    def __init__(self, ctx: ProcessingContext):
        self.ctx = ctx

    def _resolve_base(self, base: str) -> Path:
        if base == "project":
            return self.ctx.project_root
        return self.ctx.case_root

    def run(self, data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = data.copy()
        targets: Dict[str, Any] = schema or {}

        # heuristic: *_path, *_dir
        if not targets:
            for key in list(result.keys()):
                if key.endswith(("_path", "_dir")):
                    targets[key] = PathField()

        for field, meta in targets.items():
            if field in result and _is_path_field(meta):
                value = result[field]
                if isinstance(value, str):
                    base = self._resolve_base(meta.base)
                    expanded = os.path.expandvars(os.path.expanduser(value))
                    resolved = Path(expanded)
                    if not resolved.is_absolute():
                        resolved = (base / resolved).resolve()
                    result[field] = str(resolved)
        return result


class TimeProcessor:
    def __init__(self, ctx: ProcessingContext):
        self.ctx = ctx

    def run(self, data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = data.copy()
        targets: Dict[str, Any] = schema or {}

        # heuristic: *_time, *_ts, *_timestamp
        if not targets:
            for key in list(result.keys()):
                if key.endswith(("_time", "_ts", "_timestamp")):
                    targets[key] = TimeField()

        for field, meta in targets.items():
            if field in result and _is_time_field(meta):
                value = result[field]
                result[field] = self._parse_time(value, meta.unit)
        return result

    def _parse_time(self, value: Any, target_unit: str) -> float:
        tz = self.ctx.timezone

        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=tz)
            ts_seconds = dt.timestamp()
        elif isinstance(value, (int, float, str)):
            try:
                numeric = float(value)
                unit = self._infer_numeric_unit(numeric)
                ts_seconds = self._convert_numeric(numeric, unit)
            except (ValueError, TypeError):
                dt = datetime.fromisoformat(str(value).replace(" ", "T", 1))
                dt = dt if dt.tzinfo else dt.replace(tzinfo=tz)
                ts_seconds = dt.timestamp()
        else:
            raise TypeError(f"Unsupported time type: {type(value)}")

        if target_unit == "us":
            return ts_seconds * 1_000_000
        if target_unit == "ms":
            return ts_seconds * 1000
        return ts_seconds

    @staticmethod
    def _infer_numeric_unit(value: float) -> str:
        if abs(value) >= 1e15:
            return "us"
        if abs(value) >= 1e12:
            return "ms"
        return "s"

    @staticmethod
    def _convert_numeric(value: float, unit: str) -> float:
        if unit == "us":
            return value / 1_000_000
        if unit == "ms":
            return value / 1000
        return value


def process_plugin_config(
    plugin_config: Dict[str, Any],
    defaults: Dict[str, Any],
    schema: Optional[Dict[str, Any]],
    ctx: ProcessingContext,
) -> Dict[str, Any]:
    """
    Run reference, path, and time processing on a single plugin config.
    """
    resolved = ReferenceProcessor(defaults).run(plugin_config)
    resolved = PathProcessor(ctx).run(resolved, schema)
    resolved = TimeProcessor(ctx).run(resolved, schema)
    return resolved
