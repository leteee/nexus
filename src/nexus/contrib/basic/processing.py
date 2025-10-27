"""Analytics helpers for Nexus built-in processors."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def filter_dataframe(
    frame: pd.DataFrame,
    *,
    column: str,
    operator: str,
    threshold: float,
    remove_nulls: bool,
) -> pd.DataFrame:
    """Apply filtering according to configuration."""

    if remove_nulls:
        frame = frame.dropna(subset=[column])

    if operator == ">":
        return frame[frame[column] > threshold]
    if operator == "<":
        return frame[frame[column] < threshold]
    if operator == ">=":
        return frame[frame[column] >= threshold]
    if operator == "<=":
        return frame[frame[column] <= threshold]
    if operator == "==":
        return frame[frame[column] == threshold]
    if operator == "!=":
        return frame[frame[column] != threshold]

    raise ValueError(f"Unsupported operator: {operator}")


def aggregate_dataframe(
    frame: pd.DataFrame,
    *,
    group_by: str,
    agg_column: str,
    agg_function: str,
) -> pd.DataFrame:
    """Aggregate a dataframe with classic operations."""

    grouped = frame.groupby(group_by)[agg_column]
    result = grouped.aggregate(agg_function).reset_index()
    result.columns = [group_by, f"{agg_column}_{agg_function}"]
    return result


def build_validation_report(
    frame: pd.DataFrame,
    *,
    check_nulls: bool,
    check_duplicates: bool,
    check_types: bool,
    required_columns: list[str],
) -> Dict[str, Any]:
    """Validate a dataframe and return a structured report."""

    report: Dict[str, Any] = {
        "total_rows": len(frame),
        "total_columns": len(frame.columns),
        "columns": list(frame.columns),
        "checks": {},
        "issues": [],
        "passed": True,
    }

    if check_nulls:
        null_counts = frame.isnull().sum()
        null_columns = null_counts[null_counts > 0].to_dict()
        if null_columns:
            report["checks"]["nulls"] = {
                "status": "warning",
                "columns_with_nulls": null_columns,
                "total_null_values": int(null_counts.sum()),
            }
            report["issues"].append(
                f"Found null values in {len(null_columns)} columns"
            )
            report["passed"] = False
        else:
            report["checks"]["nulls"] = {
                "status": "passed",
                "message": "No null values detected",
            }

    if check_duplicates:
        duplicate_count = frame.duplicated().sum()
        if duplicate_count > 0:
            report["checks"]["duplicates"] = {
                "status": "warning",
                "duplicate_rows": int(duplicate_count),
            }
            report["issues"].append(f"Found {duplicate_count} duplicate rows")
            report["passed"] = False
        else:
            report["checks"]["duplicates"] = {
                "status": "passed",
                "message": "No duplicates detected",
            }

    if check_types:
        report["checks"]["types"] = {
            "status": "passed",
            "column_types": {col: str(dtype) for col, dtype in frame.dtypes.items()},
        }

    if required_columns:
        missing = set(required_columns) - set(frame.columns)
        if missing:
            report["checks"]["required_columns"] = {
                "status": "failed",
                "missing": sorted(missing),
            }
            report["issues"].append(f"Missing required columns: {sorted(missing)}")
            report["passed"] = False
        else:
            report["checks"]["required_columns"] = {
                "status": "passed",
                "message": "All required columns present",
            }

    return report
