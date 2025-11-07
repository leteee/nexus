# Data Generator

## Overview

Generate synthetic tabular data for testing and development.

    Creates a pandas DataFrame with numeric, categorical, and derived columns.
    Useful for testing data processing pipelines without real data.

    Generated columns:
    - numeric: Random numeric values with configurable noise
    - categorical: Categorical values with specified number of categories
    - derived: Computed columns based on other columns

    Returns:
        pandas.DataFrame with synthetic data.

## Configuration

### Example Configuration

```yaml
pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 1000  # int: Number of rows to generate
      num_categories: 5  # int: Number of categories in categorical column
      noise_level: 0.1  # float: Noise level for synthetic data (0.0 to 1.0)
      random_seed: 42  # int: Random seed for reproducible data generation
      output_data: null  # Optional[str]: Output CSV file path (None to return DataFrame without saving)
```

### Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `num_rows` | `int` | `1000` | Number of rows to generate |
| `num_categories` | `int` | `5` | Number of categories in categorical column |
| `noise_level` | `float` | `0.1` | Noise level for synthetic data (0.0 to 1.0) |
| `random_seed` | `int` | `42` | Random seed for reproducible data generation |
| `output_data` | `Optional[str]` | `null` | Output CSV file path (None to return DataFrame without saving) |

## CLI Usage

```bash
# Run with default configuration
nexus plugin "Data Generator" --case mycase

# Run with custom configuration
nexus plugin "Data Generator" --case mycase \
  -C num_rows=value \
  -C num_categories=value
```
