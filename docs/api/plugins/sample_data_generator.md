# Sample Data Generator

**Description**: 
    Generate predefined sample datasets for testing and demos.
    

## Overview

Generate predefined sample datasets for testing and demos.

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_data` | `str` | data/sample_data.csv |  |
| `dataset_type` | `str` | sales |  |
| `size` | `str` | small |  |

## Function Signature

```python
def generate_sample_dataset(ctx) -> pandas.core.frame.DataFrame:
    ...
```

## Usage Example

### CLI
```bash
nexus plugin "Sample Data Generator" --case mycase
nexus plugin "Sample Data Generator" --case mycase --config output_data=value
```

### Python API
```python
from nexus import create_engine

engine = create_engine("mycase")
result = engine.run_single_plugin("Sample Data Generator")
```
