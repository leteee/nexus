"""
Built-in data processing plugins.

These plugins provide common data transformation operations
following data_replay's plugin patterns.
"""

from typing import Annotated
import pandas as pd
import numpy as np

from nexus import plugin, PluginConfig, DataSource, DataSink


class DataCleanerConfig(PluginConfig):
    """Configuration for data cleaning operations."""

    input_data: Annotated[pd.DataFrame, DataSource(name="generated_data")]
    remove_outliers: bool = True
    outlier_threshold: float = 3.0
    fill_missing: bool = True
    missing_strategy: str = "mean"  # mean, median, mode, drop
    output_data: Annotated[str, DataSink(name="cleaned_data")] = "cleaned_data.csv"


class DataAggregatorConfig(PluginConfig):
    """Configuration for data aggregation."""

    input_data: Annotated[pd.DataFrame, DataSource(name="cleaned_data")]
    group_by_column: str = "category"
    aggregation_method: str = "mean"  # mean, sum, count, std
    output_data: Annotated[str, DataSink(name="aggregated_data")] = "aggregated_data.csv"


class DataTransformerConfig(PluginConfig):
    """Configuration for data transformation."""

    input_data: Annotated[pd.DataFrame, DataSource(name="cleaned_data")]
    normalize_columns: list[str] = []
    log_transform_columns: list[str] = []
    create_derived_features: bool = True
    output_data: Annotated[str, DataSink(name="transformed_data")] = "transformed_data.csv"


@plugin(name="Data Cleaner", config=DataCleanerConfig)
def clean_data(config: DataCleanerConfig, logger) -> pd.DataFrame:
    """
    Clean dataset by handling outliers and missing values.

    Supports multiple strategies for missing value imputation
    and outlier removal using statistical methods.
    """
    df = config.input_data.copy()
    logger.info(f"Cleaning dataset: {len(df)} rows, {len(df.columns)} columns")

    original_shape = df.shape

    # Handle missing values
    if config.fill_missing:
        missing_count = df.isnull().sum().sum()
        if missing_count > 0:
            logger.info(f"Handling {missing_count} missing values using strategy: {config.missing_strategy}")

            numeric_cols = df.select_dtypes(include=[np.number]).columns

            if config.missing_strategy == "mean":
                df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
            elif config.missing_strategy == "median":
                df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
            elif config.missing_strategy == "mode":
                for col in numeric_cols:
                    mode_value = df[col].mode()
                    if not mode_value.empty:
                        df[col] = df[col].fillna(mode_value.iloc[0])
            elif config.missing_strategy == "drop":
                df = df.dropna()

    # Remove outliers using Z-score method
    if config.remove_outliers:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col == 'id':  # Skip ID columns
                continue

            col_mean = df[col].mean()
            col_std = df[col].std()

            if col_std == 0:  # Skip columns with no variance
                continue

            z_scores = np.abs((df[col] - col_mean) / col_std)
            outlier_mask = z_scores < config.outlier_threshold
            df = df[outlier_mask]

        removed_count = original_shape[0] - len(df)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} outlier rows")

    logger.info(f"Cleaned dataset: {df.shape} (removed {original_shape[0] - df.shape[0]} rows)")
    return df


@plugin(name="Data Aggregator", config=DataAggregatorConfig)
def aggregate_data(config: DataAggregatorConfig, logger) -> pd.DataFrame:
    """
    Aggregate data by specified column using various methods.

    Supports mean, sum, count, and standard deviation aggregations
    with automatic handling of numeric and categorical columns.
    """
    df = config.input_data.copy()
    logger.info(f"Aggregating {len(df)} rows by '{config.group_by_column}' using {config.aggregation_method}")

    if config.group_by_column not in df.columns:
        raise ValueError(f"Group by column '{config.group_by_column}' not found in data")

    # Select numeric columns for aggregation
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    # Remove ID columns from aggregation
    numeric_columns = [col for col in numeric_columns if not col.lower().endswith('id')]

    # Perform aggregation
    grouped = df.groupby(config.group_by_column)

    if config.aggregation_method == "mean":
        result = grouped[numeric_columns].mean()
    elif config.aggregation_method == "sum":
        result = grouped[numeric_columns].sum()
    elif config.aggregation_method == "count":
        result = grouped[numeric_columns].count()
    elif config.aggregation_method == "std":
        result = grouped[numeric_columns].std()
    else:
        raise ValueError(f"Unsupported aggregation method: {config.aggregation_method}")

    # Reset index to make group column a regular column
    result = result.reset_index()

    # Add row count for each group
    result['row_count'] = df.groupby(config.group_by_column).size().values

    logger.info(f"Aggregated to {len(result)} groups")
    return result


@plugin(name="Data Transformer", config=DataTransformerConfig)
def transform_data(config: DataTransformerConfig, logger) -> pd.DataFrame:
    """
    Apply various transformations to the dataset.

    Supports normalization, log transformation, and creation
    of derived features based on existing columns.
    """
    df = config.input_data.copy()
    logger.info(f"Transforming dataset: {df.shape}")

    # Normalize specified columns
    for col in config.normalize_columns:
        if col in df.columns and df[col].dtype in [np.number]:
            col_min = df[col].min()
            col_max = df[col].max()
            if col_max != col_min:  # Avoid division by zero
                df[f'{col}_normalized'] = (df[col] - col_min) / (col_max - col_min)
                logger.debug(f"Normalized column '{col}'")

    # Apply log transformation
    for col in config.log_transform_columns:
        if col in df.columns and df[col].dtype in [np.number]:
            # Add 1 to handle zeros, take absolute value to handle negatives
            df[f'{col}_log'] = np.log1p(np.abs(df[col]))
            logger.debug(f"Log transformed column '{col}'")

    # Create derived features
    if config.create_derived_features:
        # Create features based on common patterns
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        if 'value' in df.columns:
            # Value-based features
            df['value_squared'] = df['value'] ** 2
            df['value_sqrt'] = np.sqrt(np.abs(df['value']))

        if 'score' in df.columns:
            # Score categories
            df['score_category'] = pd.cut(df['score'], bins=3, labels=['Low', 'Medium', 'High'])

        if len(numeric_cols) >= 2:
            # Ratio features
            first_col = numeric_cols[0]
            second_col = numeric_cols[1]
            if df[second_col].min() > 0:  # Avoid division by zero
                df[f'{first_col}_{second_col}_ratio'] = df[first_col] / df[second_col]

        logger.info("Created derived features")

    logger.info(f"Transformed dataset: {df.shape}")
    return df