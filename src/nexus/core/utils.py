"""Small shared utilities used by the core engine and CLI."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* without mutating either."""

    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def utc_now() -> datetime:
    return datetime.now(UTC)


def duration_ms(started: datetime | None, finished: datetime | None) -> float:
    if started is None or finished is None:
        return 0.0
    return max(0.0, (finished - started).total_seconds() * 1000.0)


def jsonable(value: Any, *, max_repr: int = 500) -> Any:
    """Convert arbitrary node outputs into JSON-safe values.

    Large objects (DataFrames, numpy arrays, file handles, ...) are represented
    by a bounded summary instead of being serialized wholesale.
    """

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return jsonable(value.model_dump(mode="python"), max_repr=max_repr)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return jsonable(dataclasses.asdict(value), max_repr=max_repr)
    if isinstance(value, Mapping):
        return {str(key): jsonable(item, max_repr=max_repr) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item, max_repr=max_repr) for item in value]

    # Useful summaries for common scientific/data types without importing them.
    for attr, builder in (
        ("shape", lambda obj: {"type": type(obj).__name__, "shape": list(obj.shape)}),
        ("tolist", lambda obj: {"type": type(obj).__name__, "values": obj.tolist()}),
    ):
        if hasattr(value, attr):
            try:
                summary = builder(value)
                text = json.dumps(summary, default=str)
                if len(text) <= max_repr * 4:
                    return summary
            except Exception:
                pass

    text = repr(value)
    if len(text) > max_repr:
        text = text[: max_repr - 3] + "..."
    return {"type": type(value).__name__, "repr": text}


def json_dumps(value: Any, *, indent: int | None = 2) -> str:
    return json.dumps(jsonable(value), indent=indent, ensure_ascii=False)


def format_duration(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f}ms"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, seconds = divmod(seconds, 60)
    return f"{int(minutes)}m{seconds:04.1f}s"
