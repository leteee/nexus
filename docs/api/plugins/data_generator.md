# Data Generator

## Overview

Generate synthetic dataset with configurable characteristics.

    Creates realistic test data with various data types,
    controllable noise levels, and optional outliers.

## Configuration

```yaml
pipeline:
  - plugin: "Data Generator"
    config:
      output_data: "data/generated_data.csv"  # str
      num_rows: 1000  # int
      num_categories: 5  # int
      noise_level: 0.1  # float
      random_seed: 42  # int
```

## CLI Usage

```bash
# Run with defaults
nexus plugin "Data Generator" --case mycase

# Run with custom config
nexus plugin "Data Generator" --case mycase \
  -C output_data=value \
  -C num_rows=value
```
