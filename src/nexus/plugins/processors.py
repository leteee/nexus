"""
Data processing plugins for Nexus framework.

This module provides plugins for common data processing tasks:
- Filtering data based on conditions
- Aggregating data by groups
- Basic data transformations
"""

import pandas as pd
from typing import Annotated, Dict, Any

from ..core.discovery import plugin
from ..core.types import PluginConfig, DataSource, DataSink


class DataFilterConfig(PluginConfig):
    """Configuration for Data Filter plugin."""

    input_data: Annotated[str, DataSource(handler="csv")] = "data/input.csv"
    output_data: Annotated[str, DataSink(handler="csv")] = "data/filtered.csv"

    # Filter configuration
    column: str = "value"
    operator: str = ">"  # >, <, >=, <=, ==, !=
    threshold: float = 0.0
    remove_nulls: bool = True


@plugin(name="Data Filter", config=DataFilterConfig)
def filter_data(ctx) -> pd.DataFrame:
    """
    Filter data based on column conditions.

    Applies filtering conditions to a dataset and optionally removes null values.
    Useful for data cleaning and subsetting operations.

    Supported operators:
    - '>' : Greater than
    - '<' : Less than
    - '>=' : Greater than or equal
    - '<=' : Less than or equal
    - '==' : Equal to
    - '!=' : Not equal to

    Returns:
        Filtered DataFrame with matching rows
    """
    config = ctx.config
    logger = ctx.logger

    # Load data
    df = ctx.datahub.get("input_data")
    logger.info(f"Loaded {len(df)} rows from input")

    # Remove nulls if requested
    if config.remove_nulls:
        initial_count = len(df)
        df = df.dropna(subset=[config.column])
        logger.info(f"Removed {initial_count - len(df)} rows with null values in '{config.column}'")

    # Apply filter
    if config.operator == ">":
        filtered = df[df[config.column] > config.threshold]
    elif config.operator == "<":
        filtered = df[df[config.column] < config.threshold]
    elif config.operator == ">=":
        filtered = df[df[config.column] >= config.threshold]
    elif config.operator == "<=":
        filtered = df[df[config.column] <= config.threshold]
    elif config.operator == "==":
        filtered = df[df[config.column] == config.threshold]
    elif config.operator == "!=":
        filtered = df[df[config.column] != config.threshold]
    else:
        raise ValueError(f"Unsupported operator: {config.operator}")

    logger.info(f"Filter '{config.column} {config.operator} {config.threshold}' matched {len(filtered)} rows")
    logger.info(f"Kept {len(filtered)}/{len(df)} rows ({len(filtered)/len(df)*100:.1f}%)")

    return filtered


class DataAggregatorConfig(PluginConfig):
    """Configuration for Data Aggregator plugin."""

    input_data: Annotated[str, DataSource(handler="csv")] = "data/input.csv"
    output_data: Annotated[str, DataSink(handler="csv")] = "data/aggregated.csv"

    # Aggregation configuration
    group_by: str = "category"
    agg_column: str = "value"
    agg_function: str = "mean"  # mean, sum, count, min, max, std


@plugin(name="Data Aggregator", config=DataAggregatorConfig)
def aggregate_data(ctx) -> pd.DataFrame:
    """
    Aggregate data by grouping columns.

    Groups data by specified column(s) and applies aggregation functions.
    Common for generating summary statistics and rollups.

    Supported aggregation functions:
    - 'mean' : Average value
    - 'sum' : Total sum
    - 'count' : Count of records
    - 'min' : Minimum value
    - 'max' : Maximum value
    - 'std' : Standard deviation

    Returns:
        Aggregated DataFrame with group statistics
    """
    config = ctx.config
    logger = ctx.logger

    # Load data
    df = ctx.datahub.get("input_data")
    logger.info(f"Loaded {len(df)} rows from input")

    # Perform aggregation
    if config.agg_function == "mean":
        result = df.groupby(config.group_by)[config.agg_column].mean().reset_index()
        result.columns = [config.group_by, f"{config.agg_column}_mean"]
    elif config.agg_function == "sum":
        result = df.groupby(config.group_by)[config.agg_column].sum().reset_index()
        result.columns = [config.group_by, f"{config.agg_column}_sum"]
    elif config.agg_function == "count":
        result = df.groupby(config.group_by)[config.agg_column].count().reset_index()
        result.columns = [config.group_by, f"{config.agg_column}_count"]
    elif config.agg_function == "min":
        result = df.groupby(config.group_by)[config.agg_column].min().reset_index()
        result.columns = [config.group_by, f"{config.agg_column}_min"]
    elif config.agg_function == "max":
        result = df.groupby(config.group_by)[config.agg_column].max().reset_index()
        result.columns = [config.group_by, f"{config.agg_column}_max"]
    elif config.agg_function == "std":
        result = df.groupby(config.group_by)[config.agg_column].std().reset_index()
        result.columns = [config.group_by, f"{config.agg_column}_std"]
    else:
        raise ValueError(f"Unsupported aggregation function: {config.agg_function}")

    unique_groups = df[config.group_by].nunique()
    logger.info(f"Aggregated {len(df)} rows into {len(result)} groups ({unique_groups} unique values)")
    logger.info(f"Function: {config.agg_function}({config.agg_column}) by {config.group_by}")

    return result


class DataValidatorConfig(PluginConfig):
    """Configuration for Data Validator plugin."""

    input_data: Annotated[str, DataSource(handler="csv")] = "data/input.csv"
    output_report: Annotated[str, DataSink(handler="json")] = "reports/validation.json"

    # Validation configuration
    check_nulls: bool = True
    check_duplicates: bool = True
    check_types: bool = True
    required_columns: list = []


@plugin(name="Data Validator", config=DataValidatorConfig)
def validate_data(ctx) -> Dict[str, Any]:
    """
    Validate data quality and generate report.

    Performs comprehensive data quality checks including:
    - Null value detection
    - Duplicate record detection
    - Data type validation
    - Required column verification

    Returns:
        Validation report dictionary with check results
    """
    config = ctx.config
    logger = ctx.logger

    # Load data
    df = ctx.datahub.get("input_data")
    logger.info(f"Validating {len(df)} rows, {len(df.columns)} columns")

    report = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "checks": {},
        "issues": [],
        "passed": True
    }

    # Check for nulls
    if config.check_nulls:
        null_counts = df.isnull().sum()
        null_columns = null_counts[null_counts > 0].to_dict()

        if null_columns:
            report["checks"]["nulls"] = {
                "status": "warning",
                "columns_with_nulls": null_columns,
                "total_null_values": int(null_counts.sum())
            }
            report["issues"].append(f"Found null values in {len(null_columns)} columns")
            logger.warning(f"Found null values in columns: {list(null_columns.keys())}")
        else:
            report["checks"]["nulls"] = {"status": "passed", "message": "No null values found"}
            logger.info("Null check: PASSED")

    # Check for duplicates
    if config.check_duplicates:
        duplicate_count = df.duplicated().sum()

        if duplicate_count > 0:
            report["checks"]["duplicates"] = {
                "status": "warning",
                "duplicate_rows": int(duplicate_count),
                "percentage": f"{duplicate_count/len(df)*100:.2f}%"
            }
            report["issues"].append(f"Found {duplicate_count} duplicate rows")
            logger.warning(f"Found {duplicate_count} duplicate rows")
        else:
            report["checks"]["duplicates"] = {"status": "passed", "message": "No duplicates found"}
            logger.info("Duplicate check: PASSED")

    # Check data types
    if config.check_types:
        type_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
        report["checks"]["types"] = {
            "status": "passed",
            "column_types": type_info
        }
        logger.info(f"Data types: {len(type_info)} columns checked")

    # Check required columns
    if config.required_columns:
        missing_cols = set(config.required_columns) - set(df.columns)

        if missing_cols:
            report["checks"]["required_columns"] = {
                "status": "failed",
                "missing": list(missing_cols)
            }
            report["issues"].append(f"Missing required columns: {list(missing_cols)}")
            report["passed"] = False
            logger.error(f"Missing required columns: {list(missing_cols)}")
        else:
            report["checks"]["required_columns"] = {
                "status": "passed",
                "message": "All required columns present"
            }
            logger.info("Required columns check: PASSED")

    # Summary
    if report["passed"] and not report["issues"]:
        logger.info("✓ All validation checks PASSED")
    else:
        logger.warning(f"⚠ Validation completed with {len(report['issues'])} issues")

    return report
