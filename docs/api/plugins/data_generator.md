# Data Generator

**Description**: 
    Generate synthetic dataset with configurable characteristics.

    Creates realistic test data with various data types,
    controllable noise levels, and optional outliers.
    

## Overview

Generate synthetic dataset with configurable characteristics.

    Creates realistic test data with various data types,
    controllable noise levels, and optional outliers.

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_data` | `str` | data/generated_data.csv |  |
| `num_rows` | `int` | 1000 |  |
| `num_categories` | `int` | 5 |  |
| `noise_level` | `float` | 0.1 |  |
| `random_seed` | `int` | 42 |  |

## Function Signature

```python
def generate_synthetic_data(ctx) -> pandas.core.frame.DataFrame:
    ...
```

## Usage Example

### CLI
```bash
nexus plugin "Data Generator" --case mycase
nexus plugin "Data Generator" --case mycase --config output_data=value
```

### Python API
```python
from nexus import create_engine

engine = create_engine("mycase")
result = engine.run_single_plugin("Data Generator")
```
