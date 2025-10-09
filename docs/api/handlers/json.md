# JSON Handler

## Overview

Handler for JSON files.

## Produced Type

**Type**: `dict`

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
    input_data: Annotated[str, DataSource(handler="json")] = "data/input.json"
    output_data: Annotated[str, DataSink(handler="json")] = "data/output.json"
```

### In YAML Configuration
```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      input_data: "data/input.json"
      output_data: "data/output.json"
```
