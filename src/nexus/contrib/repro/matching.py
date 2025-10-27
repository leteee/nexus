"""
Time-based data matching utilities for replay system.

Provides algorithms to match timestamped data points to video frames.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from .types import DataPoint


def match_data_to_timestamp(
    data_series: pd.DataFrame,
    timestamp_ms: float,
    *,
    tolerance_ms: float = 50.0,
    method: str = "nearest",
) -> List[DataPoint]:
    """
    Find data points matching a timestamp within tolerance.

    Args:
        data_series: DataFrame with 'timestamp_ms' column and data columns
        timestamp_ms: Target timestamp to match
        tolerance_ms: Maximum time difference to consider a match
        method: Matching method:
            - 'nearest': Find single closest point
            - 'range': Find all points within tolerance
            - 'interpolate': Linear interpolation between points

    Returns:
        List of matching DataPoint objects
    """
    if data_series.empty or "timestamp_ms" not in data_series.columns:
        return []

    if method == "nearest":
        return _match_nearest(data_series, timestamp_ms, tolerance_ms)
    elif method == "range":
        return _match_range(data_series, timestamp_ms, tolerance_ms)
    elif method == "interpolate":
        return _match_interpolate(data_series, timestamp_ms, tolerance_ms)
    else:
        raise ValueError(f"Unknown matching method: {method}")


def _match_nearest(
    data_series: pd.DataFrame,
    timestamp_ms: float,
    tolerance_ms: float,
) -> List[DataPoint]:
    """Find single nearest data point within tolerance."""
    time_diff = (data_series["timestamp_ms"] - timestamp_ms).abs()
    min_idx = time_diff.idxmin()
    min_diff = time_diff[min_idx]

    if min_diff > tolerance_ms:
        return []

    row = data_series.loc[min_idx]
    data_dict = row.drop("timestamp_ms").to_dict()

    return [DataPoint(timestamp_ms=row["timestamp_ms"], data=data_dict)]


def _match_range(
    data_series: pd.DataFrame,
    timestamp_ms: float,
    tolerance_ms: float,
) -> List[DataPoint]:
    """Find all data points within time tolerance."""
    mask = (data_series["timestamp_ms"] - timestamp_ms).abs() <= tolerance_ms
    matched_rows = data_series[mask]

    return [
        DataPoint(
            timestamp_ms=row["timestamp_ms"],
            data=row.drop("timestamp_ms").to_dict(),
        )
        for _, row in matched_rows.iterrows()
    ]


def _match_interpolate(
    data_series: pd.DataFrame,
    timestamp_ms: float,
    tolerance_ms: float,
) -> List[DataPoint]:
    """
    Interpolate data value at exact timestamp.

    Finds surrounding points and performs linear interpolation.
    """
    # Find points before and after
    before = data_series[data_series["timestamp_ms"] <= timestamp_ms]
    after = data_series[data_series["timestamp_ms"] > timestamp_ms]

    if before.empty or after.empty:
        # Fallback to nearest
        return _match_nearest(data_series, timestamp_ms, tolerance_ms)

    point_before = before.iloc[-1]
    point_after = after.iloc[0]

    # Check if interpolation range is within tolerance
    time_diff = point_after["timestamp_ms"] - point_before["timestamp_ms"]
    if time_diff > tolerance_ms * 2:
        return []

    # Linear interpolation
    t0 = point_before["timestamp_ms"]
    t1 = point_after["timestamp_ms"]
    alpha = (timestamp_ms - t0) / (t1 - t0)

    interpolated_data = {}
    for col in data_series.columns:
        if col == "timestamp_ms":
            continue

        v0 = point_before[col]
        v1 = point_after[col]

        # Only interpolate numeric values
        if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
            interpolated_data[col] = v0 + alpha * (v1 - v0)
        else:
            # Use nearest for non-numeric
            interpolated_data[col] = v0 if alpha < 0.5 else v1

    return [DataPoint(timestamp_ms=timestamp_ms, data=interpolated_data)]


def sync_data_to_frames(
    data_series: pd.DataFrame,
    frame_timestamps: pd.DataFrame,
    *,
    tolerance_ms: float = 50.0,
    method: str = "nearest",
) -> pd.DataFrame:
    """
    Synchronize data series to video frame timestamps.

    Args:
        data_series: DataFrame with timestamp_ms and data columns
        frame_timestamps: DataFrame with frame_index and timestamp_ms
        tolerance_ms: Matching tolerance
        method: Matching method (nearest, range, interpolate)

    Returns:
        DataFrame with frame_index, timestamp_ms, and matched data columns
    """
    synced_data = []

    for _, row in frame_timestamps.iterrows():
        frame_idx = row["frame_index"]
        timestamp = row["timestamp_ms"]

        matches = match_data_to_timestamp(
            data_series,
            timestamp,
            tolerance_ms=tolerance_ms,
            method=method,
        )

        if matches:
            # Take first match
            match = matches[0]
            record = {
                "frame_index": frame_idx,
                "timestamp_ms": timestamp,
                **match.data,
            }
            synced_data.append(record)

    return pd.DataFrame(synced_data)
