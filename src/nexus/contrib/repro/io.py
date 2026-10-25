"""Small JSONL helpers used by nodes and tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_jsonl(records: list[dict[str, Any]], output_path: Path | str) -> Path:
    """Write records as UTF-8 JSON Lines."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


def load_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Read a UTF-8 JSON Lines file."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
