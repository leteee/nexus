# PICKLE Handler

## Overview

Handler for pickle files.

## Produced Type

**Type**: `object`

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
    input_data: Annotated[str, DataSource(handler="pickle")] = "data/input.pickle"
    output_data: Annotated[str, DataSink(handler="pickle")] = "data/output.pickle"
```

### In YAML Configuration
```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      input_data: "data/input.pickle"
      output_data: "data/output.pickle"
```
