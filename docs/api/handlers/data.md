# DATA Handler

## Overview

Protocol for data handlers.

    Defines the interface that all data handlers must implement.
    Following data_replay's handler pattern.

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
    input_data: Annotated[str, DataSource(handler="data")] = "data/input.data"
    output_data: Annotated[str, DataSink(handler="data")] = "data/output.data"
```

### In YAML Configuration
```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      input_data: "data/input.data"
      output_data: "data/output.data"
```
