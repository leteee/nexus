"""
Nexus plugin adapters for basic contrib package.

Adapts basic data processing logic to Nexus plugin interface.
"""

from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

from nexus.contrib.basic.generation import (
    build_sample_dataset,
    build_synthetic_dataframe,
)
from nexus.contrib.basic.processing import (
    aggregate_dataframe,
    build_validation_report,
    filter_dataframe,
)


# =============================================================================
# Data Generation Plugins
# =============================================================================


class DataGeneratorConfig(PluginConfig):
    num_rows: int = 1000
    num_categories: int = 5
    noise_level: float = 0.1
    random_seed: int = 42
    output_data: str | None = None


class SampleDataGeneratorConfig(PluginConfig):
    dataset_type: str = "sales"
    size: str = "small"


@plugin(name="Data Generator", config=DataGeneratorConfig)
def generate_synthetic_data(ctx):
    """Generate synthetic data and optionally persist to CSV."""
    config = ctx.config
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
def generate_sample_dataset(ctx):
    """Produce domain-specific sample data."""
    frame = build_sample_dataset(ctx.config.dataset_type, ctx.config.size)
    ctx.remember("last_result", frame)
    return frame


# =============================================================================
# Data Processing Plugins
# =============================================================================


class DataFilterConfig(PluginConfig):
    column: str = "value"
    operator: str = ">"
    threshold: float = 0.0
    remove_nulls: bool = True


class DataAggregatorConfig(PluginConfig):
    group_by: str = "category"
    agg_column: str = "value"
    agg_function: str = "mean"


class DataValidatorConfig(PluginConfig):
    check_nulls: bool = True
    check_duplicates: bool = True
    check_types: bool = True
    required_columns: list[str] = []


@plugin(name="Data Filter", config=DataFilterConfig)
def filter_data(ctx):
    frame = ctx.recall("last_result")
    if frame is None:
        raise RuntimeError("Data Filter requires data from a previous plugin")

    filtered = filter_dataframe(
        frame,
        column=ctx.config.column,
        operator=ctx.config.operator,
        threshold=ctx.config.threshold,
        remove_nulls=ctx.config.remove_nulls,
    )

    ctx.logger.info("Filter kept %s/%s rows", len(filtered), len(frame))
    ctx.remember("last_result", filtered)
    return filtered


@plugin(name="Data Aggregator", config=DataAggregatorConfig)
def aggregate_data(ctx):
    frame = ctx.recall("last_result")
    if frame is None:
        raise RuntimeError("Data Aggregator requires data from a previous plugin")

    result = aggregate_dataframe(
        frame,
        group_by=ctx.config.group_by,
        agg_column=ctx.config.agg_column,
        agg_function=ctx.config.agg_function,
    )

    ctx.logger.info("Aggregated %s rows down to %s groups", len(frame), len(result))
    ctx.remember("last_result", result)
    return result


@plugin(name="Data Validator", config=DataValidatorConfig)
def validate_data(ctx):
    frame = ctx.recall("last_result")
    if frame is None:
        raise RuntimeError("Data Validator requires data from a previous plugin")

    report = build_validation_report(
        frame,
        check_nulls=ctx.config.check_nulls,
        check_duplicates=ctx.config.check_duplicates,
        check_types=ctx.config.check_types,
        required_columns=ctx.config.required_columns,
    )

    ctx.remember("last_result", report)
    return report
