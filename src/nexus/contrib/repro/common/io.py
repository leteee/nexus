"""
I/O utilities for loading and saving data files.

Provides functions for reading/writing JSONL, CSV, and other data formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd


def load_frame_timestamps(csv_path: Path) -> pd.DataFrame:
    """
    Load frame-to-timestamp mapping from CSV.

    Expected CSV format:
        frame_index,timestamp_ms
        0,0.0
        1,33.33
        2,66.67

    Args:
        csv_path: Path to frame timestamps CSV

    Returns:
        DataFrame with columns: frame_index, timestamp_ms
    """
    df = pd.read_csv(csv_path)
    required_cols = {"frame_index", "timestamp_ms"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required_cols}")
    return df


def load_jsonl(jsonl_path: Path) -> List[dict]:
    """
    Load time-series data from JSONL file.

    JSONL (JSON Lines) format: one JSON object per line.
    Each object must contain 'timestamp_ms' field.

    Example JSONL:
        {"timestamp_ms": 0.0, "speed": 120.5, "gps": {"lat": 39.9, "lon": 116.4}}
        {"timestamp_ms": 50.0, "speed": 125.3, "gps": {"lat": 39.91, "lon": 116.41}}

    Args:
        jsonl_path: Path to JSONL file

    Returns:
        List of data dictionaries sorted by timestamp_ms

    Raises:
        ValueError: If any record is missing timestamp_ms
    """
    import json

    data = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}")

            if "timestamp_ms" not in record:
                raise ValueError(
                    f"Line {line_num} missing required field 'timestamp_ms'"
                )

            data.append(record)

    # Sort by timestamp
    data.sort(key=lambda x: x["timestamp_ms"])
    return data


def save_jsonl(data: List[dict], jsonl_path: Path) -> None:
    """
    Save data to JSONL file.

    Args:
        data: List of dictionaries to save
        jsonl_path: Output path for JSONL file
    """
    import json

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for record in data:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
