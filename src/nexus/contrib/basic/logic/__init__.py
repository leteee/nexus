"""Public exports for built-in business logic."""

from .generation import build_sample_dataset, build_synthetic_dataframe
from .processing import (
    aggregate_dataframe,
    build_validation_report,
    filter_dataframe,
)

__all__ = [
    "build_sample_dataset",
    "build_synthetic_dataframe",
    "aggregate_dataframe",
    "build_validation_report",
    "filter_dataframe",
]
