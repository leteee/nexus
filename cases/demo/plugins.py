"""
Demo plugins for the Nexus framework.

These plugins demonstrate common data processing patterns
and serve as examples for building custom processing workflows.
"""

from typing import Annotated, Optional
import pandas as pd
import numpy as np

from nexus.plugins import plugin
from nexus.typing import PluginConfig, DataSource, DataSink


class DataGeneratorConfig(PluginConfig):
    """Configuration for generating sample data."""
    num_rows: int = 1000
    num_categories: int = 5
    noise_level: float = 0.1


class DataCleanerConfig(PluginConfig):
    """Configuration for data cleaning operations."""
    raw_data: Annotated[pd.DataFrame, DataSource(name="raw_dataset")]
    remove_outliers: bool = True
    outlier_threshold: float = 3.0


class AggregatorConfig(PluginConfig):
    """Configuration for data aggregation."""
    clean_data: Annotated[pd.DataFrame, DataSource(name="cleaned_dataset")]
    group_by_column: str = "category"
    aggregation_method: str = "mean"


@plugin(name="Data Generator", config=DataGeneratorConfig)
def generate_sample_data(config: DataGeneratorConfig, logger) -> pd.DataFrame:
    """
    Generate sample dataset for demonstration.

    Creates a synthetic dataset with various columns and some noise
    to simulate real-world data characteristics.
    """
    logger.info(f"Generating {config.num_rows} rows of sample data")

    np.random.seed(42)  # For reproducible results

    # Generate base data
    data = {
        'id': range(1, config.num_rows + 1),
        'category': np.random.choice(
            [f'Cat_{i}' for i in range(config.num_categories)],
            config.num_rows
        ),
        'value': np.random.normal(100, 20, config.num_rows),
        'score': np.random.uniform(0, 1, config.num_rows),
        'timestamp': pd.date_range(
            '2024-01-01',
            periods=config.num_rows,
            freq='1H'
        )
    }

    df = pd.DataFrame(data)

    # Add some noise and outliers
    if config.noise_level > 0:
        noise = np.random.normal(0, config.noise_level * df['value'].std(), config.num_rows)
        df['value'] += noise

        # Add a few outliers
        outlier_indices = np.random.choice(config.num_rows, size=int(config.num_rows * 0.02))
        df.loc[outlier_indices, 'value'] *= np.random.choice([5, -5], len(outlier_indices))

    logger.info(f"Generated dataset with shape {df.shape}")
    return df


@plugin(name="Data Cleaner", config=DataCleanerConfig)
def clean_data(config: DataCleanerConfig, logger) -> pd.DataFrame:
    """
    Clean the input dataset by removing outliers and handling missing values.
    """
    df = config.raw_data.copy()
    logger.info(f"Cleaning dataset with {len(df)} rows")

    original_count = len(df)

    # Remove outliers using Z-score method
    if config.remove_outliers:
        z_scores = np.abs((df['value'] - df['value'].mean()) / df['value'].std())
        outlier_mask = z_scores < config.outlier_threshold
        df = df[outlier_mask]
        removed_count = original_count - len(df)
        logger.info(f"Removed {removed_count} outliers")

    # Handle missing values (if any)
    missing_count = df.isnull().sum().sum()
    if missing_count > 0:
        df = df.dropna()
        logger.info(f"Removed {missing_count} rows with missing values")

    # Add derived features
    df['value_normalized'] = (df['value'] - df['value'].min()) / (df['value'].max() - df['value'].min())
    df['score_category'] = pd.cut(df['score'], bins=3, labels=['Low', 'Medium', 'High'])

    logger.info(f"Cleaned dataset has {len(df)} rows")
    return df


@plugin(name="Data Aggregator", config=AggregatorConfig)
def aggregate_data(config: AggregatorConfig, logger) -> pd.DataFrame:
    """
    Aggregate data by specified grouping column and method.
    """
    df = config.clean_data.copy()
    logger.info(f"Aggregating {len(df)} rows by {config.group_by_column}")

    # Perform aggregation
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    numeric_columns = [col for col in numeric_columns if col != 'id']

    if config.aggregation_method == "mean":
        result = df.groupby(config.group_by_column)[numeric_columns].mean()
    elif config.aggregation_method == "sum":
        result = df.groupby(config.group_by_column)[numeric_columns].sum()
    elif config.aggregation_method == "count":
        result = df.groupby(config.group_by_column)[numeric_columns].count()
    else:
        raise ValueError(f"Unsupported aggregation method: {config.aggregation_method}")

    # Reset index to make group column a regular column
    result = result.reset_index()

    # Add summary statistics
    result['total_count'] = df.groupby(config.group_by_column).size().values

    logger.info(f"Aggregated to {len(result)} groups")
    logger.info(f"Aggregation result shape: {result.shape}")

    return result


@plugin(name="Statistical Analyzer", config=DataCleanerConfig)
def analyze_statistics(config: DataCleanerConfig, logger) -> dict:
    """
    Perform statistical analysis on the dataset.
    """
    df = config.raw_data.copy()
    logger.info(f"Analyzing statistics for dataset with {len(df)} rows")

    stats = {
        'basic_stats': {
            'row_count': len(df),
            'column_count': len(df.columns),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
        },
        'numeric_stats': {},
        'categorical_stats': {}
    }

    # Numeric column statistics
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        stats['numeric_stats'][col] = {
            'mean': float(df[col].mean()),
            'median': float(df[col].median()),
            'std': float(df[col].std()),
            'min': float(df[col].min()),
            'max': float(df[col].max()),
            'null_count': int(df[col].isnull().sum())
        }

    # Categorical column statistics
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    for col in categorical_cols:
        stats['categorical_stats'][col] = {
            'unique_count': int(df[col].nunique()),
            'most_frequent': str(df[col].mode().iloc[0] if not df[col].mode().empty else 'N/A'),
            'null_count': int(df[col].isnull().sum())
        }

    logger.info("Statistical analysis completed")
    return stats