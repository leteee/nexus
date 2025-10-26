"""Framework-independent data generation utilities for built-in plugins."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_synthetic_dataframe(
    *,
    num_rows: int,
    num_categories: int,
    noise_level: float,
    random_seed: int,
) -> pd.DataFrame:
    """Generate a reproducible synthetic dataset."""

    rng = np.random.default_rng(random_seed)
    categories = [f"Category_{i}" for i in range(num_categories)]

    frame = pd.DataFrame(
        {
            "id": np.arange(1, num_rows + 1),
            "category": rng.choice(categories, num_rows),
            "value": rng.normal(100, 20, num_rows),
            "score": rng.random(num_rows),
            "timestamp": pd.date_range("2024-01-01", periods=num_rows, freq="1h"),
            "is_active": rng.choice([True, False], num_rows, p=[0.7, 0.3]),
        }
    )

    if noise_level > 0:
        noise = rng.normal(0, noise_level * frame["value"].std(), num_rows)
        frame["value"] += noise

    return frame


def build_sample_dataset(dataset_type: str, size: str) -> pd.DataFrame:
    """Generate domain-specific sample datasets."""

    size_mapping = {"small": 100, "medium": 1_000, "large": 10_000}
    num_rows = size_mapping.get(size, 100)

    if dataset_type == "sales":
        return _generate_sales_data(num_rows)
    if dataset_type == "customers":
        return _generate_customer_data(num_rows)
    if dataset_type == "products":
        return _generate_product_data(num_rows)

    raise ValueError(f"Unknown dataset type: {dataset_type}")


def _generate_sales_data(num_rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    products = ["Product_A", "Product_B", "Product_C", "Product_D", "Product_E"]
    regions = ["North", "South", "East", "West", "Central"]

    frame = pd.DataFrame(
        {
            "sale_id": np.arange(1, num_rows + 1),
            "product": rng.choice(products, num_rows),
            "region": rng.choice(regions, num_rows),
            "quantity": rng.integers(1, 100, num_rows),
            "unit_price": rng.uniform(10, 500, num_rows).round(2),
            "sale_date": pd.date_range("2024-01-01", periods=num_rows, freq="1H"),
            "customer_type": rng.choice(["Premium", "Standard", "Basic"], num_rows, p=[0.2, 0.5, 0.3]),
        }
    )
    frame["total_amount"] = (frame["quantity"] * frame["unit_price"]).round(2)
    return frame


def _generate_customer_data(num_rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(24)
    first_names = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana", "Eve", "Frank"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia"]

    frame = pd.DataFrame(
        {
            "customer_id": np.arange(1, num_rows + 1),
            "first_name": rng.choice(first_names, num_rows),
            "last_name": rng.choice(last_names, num_rows),
            "age": rng.integers(18, 80, num_rows),
            "city": rng.choice(cities, num_rows),
            "registration_date": pd.date_range("2020-01-01", periods=num_rows, freq="1D"),
            "is_premium": rng.choice([True, False], num_rows, p=[0.3, 0.7]),
            "lifetime_value": rng.exponential(1000, num_rows).round(2),
        }
    )
    return frame


def _generate_product_data(num_rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    categories = ["Electronics", "Clothing", "Home", "Sports", "Books", "Health"]
    brands = ["BrandA", "BrandB", "BrandC", "BrandD", "BrandE"]

    frame = pd.DataFrame(
        {
            "product_id": np.arange(1, num_rows + 1),
            "product_name": [f"Product_{i}" for i in range(1, num_rows + 1)],
            "category": rng.choice(categories, num_rows),
            "brand": rng.choice(brands, num_rows),
            "price": rng.uniform(5, 2000, num_rows).round(2),
            "stock_quantity": rng.integers(0, 1000, num_rows),
            "rating": rng.uniform(1, 5, num_rows).round(1),
            "launch_date": pd.date_range("2020-01-01", periods=num_rows, freq="7D"),
        }
    )
    frame["cost"] = (frame["price"] * rng.uniform(0.3, 0.8, num_rows)).round(2)
    frame["margin"] = ((frame["price"] - frame["cost"]) / frame["price"] * 100).round(1)
    return frame
