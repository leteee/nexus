# PARQUET Handler

## Overview

Handler for Parquet files using pandas.

## Produced Type

**Type**: `DataFrame`

## Methods

### `load(path: Path) -> Any`
Load data from the specified file path.

### `save(data: Any, path: Path) -> None`
Save data to the specified file path.

## Usage Example

### In Plugin Configuration
```python
from typing import Annotated
from nexus import PluginConfig, DataSource, DataSink

class MyConfig(PluginConfig):
    input_data: Annotated[str, DataSource(handler="parquet")] = "data/input.parquet"
    output_data: Annotated[str, DataSink(handler="parquet")] = "data/output.parquet"
```

### In YAML Configuration
```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      input_data: "data/input.parquet"
      output_data: "data/output.parquet"
```
