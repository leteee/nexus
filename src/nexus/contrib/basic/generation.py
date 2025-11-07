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
