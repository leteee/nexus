# Sample Data Generator

## Overview

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

## Configuration

### Example Configuration

```yaml
pipeline:
  - plugin: "Sample Data Generator"
    config:
      dataset_type: "sales"  # str: Type of sample dataset to generate (e.g., 'sales', 'customer', 'product')
      size: "small"  # str: Dataset size category ('small', 'medium', 'large')
```

### Field Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dataset_type` | `str` | `"sales"` | Type of sample dataset to generate (e.g., 'sales', 'customer', 'product') |
| `size` | `str` | `"small"` | Dataset size category ('small', 'medium', 'large') |

## CLI Usage

```bash
# Run with default configuration
nexus plugin "Sample Data Generator" --case mycase

# Run with custom configuration
nexus plugin "Sample Data Generator" --case mycase \
  -C dataset_type=value \
  -C size=value
```
