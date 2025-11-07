"""
Nexus plugin adapters for basic contrib package.

Adapts basic data processing logic to Nexus plugin interface.
"""

from typing import Any, Optional

from pydantic import Field

from nexus.core.context import PluginContext
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

from nexus.contrib.basic.generation import (
    build_sample_dataset,
    build_synthetic_dataframe,
)


# =============================================================================
# Data Generation Plugins
# =============================================================================


class DataGeneratorConfig(PluginConfig):
    """Configuration for synthetic data generation."""

    num_rows: int = Field(
        default=1000,
        ge=1,
        le=1000000,
        description="Number of rows to generate"
    )
    num_categories: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of categories in categorical column"
    )
    noise_level: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Noise level for synthetic data (0.0 to 1.0)"
    )
    random_seed: int = Field(
        default=42,
        description="Random seed for reproducible data generation"
    )
    output_data: Optional[str] = Field(
        default=None,
        description="Output CSV file path (None to return DataFrame without saving)"
    )


class SampleDataGeneratorConfig(PluginConfig):
    """Configuration for domain-specific sample data generation."""

    dataset_type: str = Field(
        default="sales",
        description="Type of sample dataset to generate (e.g., 'sales', 'customer', 'product')"
    )
    size: str = Field(
        default="small",
        description="Dataset size category ('small', 'medium', 'large')"
    )


@plugin(name="Data Generator", config=DataGeneratorConfig)
def generate_synthetic_data(ctx: PluginContext) -> Any:
    """
    Generate synthetic tabular data for testing and development.

    Creates a pandas DataFrame with numeric, categorical, and derived columns.
    Useful for testing data processing pipelines without real data.

    Generated columns:
    - numeric: Random numeric values with configurable noise
    - categorical: Categorical values with specified number of categories
    - derived: Computed columns based on other columns

    Returns:
        pandas.DataFrame with synthetic data.
    """
    config: DataGeneratorConfig = ctx.config  # type: ignore
    frame = build_synthetic_dataframe(
        num_rows=config.num_rows,
        num_categories=config.num_categories,
        noise_level=config.noise_level,
        random_seed=config.random_seed,
    )

    if config.output_data:
        output_path = ctx.resolve_path(config.output_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
        ctx.logger.info("Wrote dataset to %s", output_path)

    ctx.remember("last_result", frame)
    return frame


@plugin(name="Sample Data Generator", config=SampleDataGeneratorConfig)
def generate_sample_dataset(ctx: PluginContext) -> Any:
    """
    Generate domain-specific sample datasets.

    Creates realistic sample data for common business domains.
    Useful for demonstrations, testing, and prototyping.

    Supported dataset types:
    - sales: Sales transaction data with products, dates, quantities
    - customer: Customer information with demographics
    - product: Product catalog with pricing and categories

    Size categories determine the number of rows:
    - small: ~100 rows
    - medium: ~1000 rows
    - large: ~10000 rows

    Returns:
        pandas.DataFrame with domain-specific sample data.
    """
    config: SampleDataGeneratorConfig = ctx.config  # type: ignore
    frame = build_sample_dataset(config.dataset_type, config.size)
    ctx.remember("last_result", frame)
    return frame
