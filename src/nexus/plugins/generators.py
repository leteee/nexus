"""
Built-in data generation plugins.

These plugins demonstrate best practices and provide commonly needed
data generation capabilities.
"""

from typing import Annotated

import numpy as np
import pandas as pd

from nexus import DataSink, PluginConfig, plugin


class DataGeneratorConfig(PluginConfig):
    """Configuration for synthetic data generation."""

    # Output configuration
    output_data: Annotated[str, DataSink(handler="csv")] = "data/generated_data.csv"

    # Behavior configuration
    num_rows: int = 1000
    num_categories: int = 5
    noise_level: float = 0.1
    random_seed: int = 42


class SampleDataGeneratorConfig(PluginConfig):
    """Configuration for sample dataset generation."""

    # Output configuration
    output_data: Annotated[str, DataSink(handler="csv")] = "data/sample_data.csv"

    # Behavior configuration
    dataset_type: str = "sales"  # sales, customers, products
    size: str = "small"  # small, medium, large


@plugin(name="Data Generator", config=DataGeneratorConfig)
def generate_synthetic_data(ctx) -> pd.DataFrame:
    """
    Generate synthetic dataset with configurable characteristics.

    Creates realistic test data with various data types,
    controllable noise levels, and optional outliers.
    """
    config = ctx.config
    logger = ctx.logger

    logger.info(
        f"Generating {config.num_rows} rows with {config.num_categories} categories"
    )

    np.random.seed(config.random_seed)

    # Generate base dataset
    data = {
        "id": range(1, config.num_rows + 1),
        "category": np.random.choice(
            [f"Category_{i}" for i in range(config.num_categories)], config.num_rows
        ),
        "value": np.random.normal(100, 20, config.num_rows),
        "score": np.random.uniform(0, 1, config.num_rows),
        "timestamp": pd.date_range("2024-01-01", periods=config.num_rows, freq="1h"),
        "is_active": np.random.choice([True, False], config.num_rows, p=[0.7, 0.3]),
    }

    df = pd.DataFrame(data)

    # Add configurable noise
    if config.noise_level > 0:
        noise = np.random.normal(
            0, config.noise_level * df["value"].std(), config.num_rows
        )
        df["value"] += noise

        # Add some outliers
        outlier_count = max(1, int(config.num_rows * 0.02))
        outlier_indices = np.random.choice(
            config.num_rows, size=outlier_count, replace=False
        )
        df.loc[outlier_indices, "value"] *= np.random.choice(
            [5, -3], len(outlier_indices)
        )

    logger.info(
        f"Generated dataset: shape={df.shape}, memory={df.memory_usage(deep=True).sum() / 1024:.1f}KB"
    )
    return df


@plugin(name="Sample Data Generator", config=SampleDataGeneratorConfig)
def generate_sample_dataset(ctx) -> pd.DataFrame:
    """
    Generate predefined sample datasets for testing and demos.
    """
    config = ctx.config
    logger = ctx.logger

    logger.info(f"Generating {config.dataset_type} dataset, size: {config.size}")

    size_mapping = {"small": 100, "medium": 1000, "large": 10000}

    num_rows = size_mapping.get(config.size, 100)
    np.random.seed(42)  # Consistent sample data

    if config.dataset_type == "sales":
        return _generate_sales_data(num_rows, logger)
    elif config.dataset_type == "customers":
        return _generate_customer_data(num_rows, logger)
    elif config.dataset_type == "products":
        return _generate_product_data(num_rows, logger)
    else:
        raise ValueError(f"Unknown dataset type: {config.dataset_type}")


def _generate_sales_data(num_rows: int, logger) -> pd.DataFrame:
    """Generate sample sales data."""
    logger.debug(f"Generating {num_rows} sales records")

    products = ["Product_A", "Product_B", "Product_C", "Product_D", "Product_E"]
    regions = ["North", "South", "East", "West", "Central"]

    data = {
        "sale_id": range(1, num_rows + 1),
        "product": np.random.choice(products, num_rows),
        "region": np.random.choice(regions, num_rows),
        "quantity": np.random.randint(1, 100, num_rows),
        "unit_price": np.random.uniform(10, 500, num_rows).round(2),
        "sale_date": pd.date_range("2024-01-01", periods=num_rows, freq="1H"),
        "customer_type": np.random.choice(
            ["Premium", "Standard", "Basic"], num_rows, p=[0.2, 0.5, 0.3]
        ),
    }

    df = pd.DataFrame(data)
    df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)

    return df


def _generate_customer_data(num_rows: int, logger) -> pd.DataFrame:
    """Generate sample customer data."""
    logger.debug(f"Generating {num_rows} customer records")

    first_names = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana", "Eve", "Frank"]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
    ]
    cities = [
        "New York",
        "Los Angeles",
        "Chicago",
        "Houston",
        "Phoenix",
        "Philadelphia",
    ]

    data = {
        "customer_id": range(1, num_rows + 1),
        "first_name": np.random.choice(first_names, num_rows),
        "last_name": np.random.choice(last_names, num_rows),
        "age": np.random.randint(18, 80, num_rows),
        "city": np.random.choice(cities, num_rows),
        "registration_date": pd.date_range("2020-01-01", periods=num_rows, freq="1D"),
        "is_premium": np.random.choice([True, False], num_rows, p=[0.3, 0.7]),
        "lifetime_value": np.random.exponential(1000, num_rows).round(2),
    }

    return pd.DataFrame(data)


def _generate_product_data(num_rows: int, logger) -> pd.DataFrame:
    """Generate sample product data."""
    logger.debug(f"Generating {num_rows} product records")

    categories = ["Electronics", "Clothing", "Home", "Sports", "Books", "Health"]
    brands = ["BrandA", "BrandB", "BrandC", "BrandD", "BrandE"]

    data = {
        "product_id": range(1, num_rows + 1),
        "product_name": [f"Product_{i}" for i in range(1, num_rows + 1)],
        "category": np.random.choice(categories, num_rows),
        "brand": np.random.choice(brands, num_rows),
        "price": np.random.uniform(5, 2000, num_rows).round(2),
        "stock_quantity": np.random.randint(0, 1000, num_rows),
        "rating": np.random.uniform(1, 5, num_rows).round(1),
        "launch_date": pd.date_range("2020-01-01", periods=num_rows, freq="7D"),
    }

    df = pd.DataFrame(data)
    df["cost"] = (df["price"] * np.random.uniform(0.3, 0.8, num_rows)).round(2)
    df["margin"] = ((df["price"] - df["cost"]) / df["price"] * 100).round(1)

    return df
