"""
Nexus plugin adapters for basic contrib package.

Adapts basic data processing logic to Nexus plugin interface.
"""

from typing import Any, Optional

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
    num_rows: int = 1000
    num_categories: int = 5
    noise_level: float = 0.1
    random_seed: int = 42
    output_data: Optional[str] = None


class SampleDataGeneratorConfig(PluginConfig):
    dataset_type: str = "sales"
    size: str = "small"


@plugin(name="Data Generator", config=DataGeneratorConfig)
def generate_synthetic_data(ctx: PluginContext) -> Any:
    """Generate synthetic data and optionally persist to CSV."""
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
    """Produce domain-specific sample data."""
    config: SampleDataGeneratorConfig = ctx.config  # type: ignore
    frame = build_sample_dataset(config.dataset_type, config.size)
    ctx.remember("last_result", frame)
    return frame
