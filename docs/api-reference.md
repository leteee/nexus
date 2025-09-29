# API Reference

Complete reference for the Nexus framework API.

## Core Components

### nexus.create_engine()

```python
def create_engine(
    project_root: Optional[Path] = None,
    case_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> PipelineEngine
```

Create a PipelineEngine instance for executing plugins and pipelines.

**Parameters:**
- `project_root` (Path, optional): Path to project root directory. Auto-detected if None by looking for `pyproject.toml`.
- `case_path` (Path, optional): Path to case directory. Defaults to `{project_root}/cases/default`.
- `logger` (Logger, optional): Custom logger instance. Creates default logger if None.

**Returns:**
- `PipelineEngine`: Configured engine instance.

**Raises:**
- `ValueError`: If project root cannot be determined.

**Example:**
```python
import nexus
from pathlib import Path

# Auto-detect project root
engine = nexus.create_engine()

# Specify custom paths
engine = nexus.create_engine(
    project_root=Path("/my/project"),
    case_path=Path("/my/project/cases/analysis")
)
```

### nexus.run_plugin()

```python
def run_plugin(
    plugin_name: str,
    config_overrides: Optional[Dict[str, Any]] = None,
    case_path: Optional[Path] = None,
    project_root: Optional[Path] = None
) -> Any
```

Execute a single plugin programmatically.

**Parameters:**
- `plugin_name` (str): Name of the plugin to execute.
- `config_overrides` (Dict, optional): Configuration overrides for the plugin.
- `case_path` (Path, optional): Path to case directory.
- `project_root` (Path, optional): Path to project root.

**Returns:**
- `Any`: Plugin execution result.

**Example:**
```python
# Run with default configuration
result = nexus.run_plugin("Data Generator")

# Run with custom configuration
result = nexus.run_plugin("Data Generator", {
    "num_rows": 5000,
    "num_categories": 3,
    "random_seed": 123
})
```

### nexus.run_pipeline()

```python
def run_pipeline(
    case_path: Optional[Path] = None,
    pipeline_config: Optional[Path] = None,
    config_overrides: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None
) -> None
```

Execute a complete pipeline programmatically.

**Parameters:**
- `case_path` (Path, optional): Path to case directory.
- `pipeline_config` (Path, optional): Path to pipeline configuration file.
- `config_overrides` (Dict, optional): Configuration overrides.
- `project_root` (Path, optional): Path to project root.

**Example:**
```python
# Run default pipeline
nexus.run_pipeline()

# Run with overrides
nexus.run_pipeline(
    case_path=Path("cases/my_analysis"),
    config_overrides={
        "plugins": {
            "Data Generator": {"num_rows": 10000}
        }
    }
)
```

## Plugin System

### @plugin Decorator

```python
def plugin(
    *,
    name: str,
    config: type = None,
    description: str = None,
    output_key: str = None
)
```

Decorator to register a function as a plugin.

**Parameters:**
- `name` (str): Unique name for the plugin.
- `config` (type, optional): Pydantic model class for plugin configuration.
- `description` (str, optional): Plugin description. Uses function docstring if not provided.
- `output_key` (str, optional): Key for storing plugin output in DataHub.

**Example:**
```python
from nexus import plugin, PluginConfig

class MyConfig(PluginConfig):
    threshold: float = 0.5

@plugin(name="My Plugin", config=MyConfig, description="Processes data")
def my_plugin(config: MyConfig, logger) -> pd.DataFrame:
    return config.input_data[config.input_data["value"] > config.threshold]
```

### nexus.get_plugin()

```python
def get_plugin(name: str) -> PluginSpec
```

Retrieve a plugin specification by name.

**Parameters:**
- `name` (str): Plugin name.

**Returns:**
- `PluginSpec`: Plugin specification.

**Raises:**
- `KeyError`: If plugin not found.

### nexus.list_plugins()

```python
def list_plugins() -> Dict[str, PluginSpec]
```

Get all registered plugins.

**Returns:**
- `Dict[str, PluginSpec]`: Dictionary mapping plugin names to specifications.

## Configuration Classes

### PluginConfig

```python
class PluginConfig(BaseModel):
    """Base configuration class for all plugins."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True
    )
```

Base class for all plugin configurations. Inherits from Pydantic's `BaseModel`.

**Features:**
- Automatic validation of field types
- Forbids extra fields not defined in model
- Validates assignments after model creation

**Example:**
```python
from nexus import PluginConfig, DataSource, DataSink
from typing import Annotated

class MyPluginConfig(PluginConfig):
    input_data: Annotated[pd.DataFrame, DataSource(name="source")]
    threshold: float = 0.5
    output_path: Annotated[str, DataSink(name="result")] = "output.csv"
```

## Type Annotations

### DataSource

```python
class DataSource:
    def __init__(self, name: str, handler_args: Optional[Dict[str, Any]] = None)
```

Annotation for marking data source dependencies.

**Parameters:**
- `name` (str): Name of the data source in configuration.
- `handler_args` (Dict, optional): Additional arguments for data handler.

**Example:**
```python
from typing import Annotated
import pandas as pd

class Config(PluginConfig):
    # Basic data source
    data: Annotated[pd.DataFrame, DataSource(name="input_data")]

    # Data source with handler arguments
    csv_data: Annotated[
        pd.DataFrame,
        DataSource(name="csv_file", handler_args={"sep": ";", "encoding": "utf-8"})
    ]
```

### DataSink

```python
class DataSink:
    def __init__(self, name: str, handler_args: Optional[Dict[str, Any]] = None)
```

Annotation for marking data output destinations.

**Parameters:**
- `name` (str): Name of the data sink in configuration.
- `handler_args` (Dict, optional): Additional arguments for data handler.

**Example:**
```python
class Config(PluginConfig):
    # Basic data sink
    output: Annotated[str, DataSink(name="result")] = "output.csv"

    # Data sink with handler arguments
    parquet_output: Annotated[
        str,
        DataSink(name="data", handler_args={"compression": "snappy"})
    ] = "data.parquet"
```

## Core Classes

### PipelineEngine

```python
class PipelineEngine:
    def __init__(
        self,
        project_root: Path,
        case_path: Path,
        logger_instance: Optional[logging.Logger] = None,
    )
```

Core pipeline execution engine.

#### Methods

##### run_pipeline()

```python
def run_pipeline(
    self,
    pipeline_config_path: Optional[Path] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> None
```

Execute a complete pipeline from configuration.

##### run_plugin()

```python
def run_plugin(
    self,
    plugin_name: str,
    config_overrides: Optional[Dict[str, Any]] = None,
) -> Any
```

Execute a single plugin with configuration overrides.

### DataHub

```python
class DataHub:
    def __init__(
        self,
        project_root: Path,
        case_path: Path,
        logger: logging.Logger
    )
```

Centralized data management with lazy loading and caching.

#### Methods

##### get()

```python
def get(self, name: str) -> Any
```

Load data by name. Uses lazy loading and caching.

**Parameters:**
- `name` (str): Data source name.

**Returns:**
- `Any`: Loaded data.

**Raises:**
- `FileNotFoundError`: If required data source not found.

##### save()

```python
def save(self, name: str, data: Any) -> None
```

Save data to registered data sink.

**Parameters:**
- `name` (str): Data sink name.
- `data` (Any): Data to save.

##### register_source()

```python
def register_source(
    self,
    name: str,
    path: str,
    handler_type: str,
    must_exist: bool = True
) -> None
```

Register a data source for later loading.

## Context Classes

### NexusContext

```python
@dataclass(frozen=True)
class NexusContext:
    project_root: Path
    case_path: Path
    logger: Logger
    run_config: Dict[str, Any] = field(default_factory=dict)
```

Immutable context containing framework-wide information.

#### Methods

##### create_datahub()

```python
def create_datahub(self) -> DataHub
```

Create a DataHub instance from this context.

### PluginContext

```python
@dataclass(frozen=True)
class PluginContext:
    nexus_context: NexusContext
    datahub: DataHub
    config: Optional[PluginConfig] = None
```

Immutable context passed to plugin functions.

#### Class Methods

##### from_nexus_context()

```python
@classmethod
def from_nexus_context(
    cls,
    nexus_context: NexusContext,
    datahub: DataHub,
    config: Optional[PluginConfig] = None,
) -> "PluginContext"
```

Create PluginContext from NexusContext.

## Data Handlers

### DataHandler Protocol

```python
@runtime_checkable
class DataHandler(Protocol):
    def load(self, path: Path) -> Any: ...
    def save(self, data: Any, path: Path) -> None: ...
    @property
    def produced_type(self) -> type: ...
```

Protocol for implementing custom data handlers.

#### Built-in Handlers

##### CSVHandler

Handles CSV files using pandas.

**Features:**
- Automatic type inference
- Configurable separator and encoding
- Index handling

**Handler Args:**
- `sep` (str): Column separator (default: ",")
- `encoding` (str): File encoding (default: "utf-8")
- `index` (bool): Whether to save index (default: False)

##### JSONHandler

Handles JSON files.

**Features:**
- Structured data support
- Pretty printing option
- Custom serialization

**Handler Args:**
- `indent` (int): JSON indentation (default: 2)
- `ensure_ascii` (bool): ASCII encoding (default: False)

##### ParquetHandler

Handles Parquet files using pandas and pyarrow.

**Features:**
- Efficient columnar storage
- Compression support
- Schema preservation

**Handler Args:**
- `compression` (str): Compression method (default: "snappy")
- `engine` (str): Parquet engine (default: "pyarrow")

## Configuration Functions

### create_configuration_context()

```python
@lru_cache(maxsize=128)
def create_configuration_context(
    project_root_str: str,
    case_path_str: str,
    plugin_registry_hash: str,
    discovered_sources_hash: str,
    cli_args_hash: str,
) -> Dict[str, Any]
```

Create immutable configuration context with caching.

**Returns:**
- `Dict[str, Any]`: Configuration context containing global and case configurations.

### merge_configurations()

```python
def merge_configurations(
    case_config: Dict[str, Any],
    global_config: Dict[str, Any],
    plugin_defaults: Dict[str, Dict],
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

Merge configuration layers with proper precedence.

**Parameters:**
- `case_config` (Dict): Case-specific configuration.
- `global_config` (Dict): Global configuration.
- `plugin_defaults` (Dict): Plugin default configurations.
- `cli_overrides` (Dict, optional): CLI argument overrides.

**Returns:**
- `Dict[str, Any]`: Merged configuration.

## Discovery Functions

### auto_discover_data_sources()

```python
def auto_discover_data_sources(plugin_names: List[str]) -> Dict[str, Dict]
```

Automatically discover data sources from plugin annotations.

**Parameters:**
- `plugin_names` (List[str]): List of plugin names to analyze.

**Returns:**
- `Dict[str, Dict]`: Discovered data source configurations.

## Error Classes

### NexusError

```python
class NexusError(Exception):
    """Base exception for Nexus framework."""
```

### ConfigurationError

```python
class ConfigurationError(NexusError):
    """Raised when configuration is invalid."""
```

### PluginError

```python
class PluginError(NexusError):
    """Raised when plugin execution fails."""
```

### DataSourceError

```python
class DataSourceError(NexusError):
    """Raised when data source operations fail."""
```

## CLI Interface

### Commands

#### nexus run

Execute a pipeline.

```bash
nexus run [OPTIONS]

Options:
  --case, -c PATH         Case directory path
  --pipeline, -p PATH     Pipeline configuration file
  --config KEY=VALUE      Configuration overrides
  --log-level LEVEL       Logging level (DEBUG, INFO, WARNING, ERROR)
```

#### nexus plugin

Execute a single plugin.

```bash
nexus plugin [OPTIONS] PLUGIN_NAME

Options:
  --case, -c PATH         Case directory path
  --config KEY=VALUE      Configuration overrides
  --log-level LEVEL       Logging level
```

#### nexus list

List available plugins.

```bash
nexus list [OPTIONS]

Options:
  --case, -c PATH         Case directory path
```

## Environment Variables

- `NEXUS_LOG_LEVEL`: Default logging level
- `NEXUS_CONFIG_PATH`: Default global configuration path
- `NEXUS_CASE_PATH`: Default case path

## Configuration Schema

### Global Configuration (config/global.yaml)

```yaml
framework:
  name: str
  version: str
  logging:
    level: str
    format: str

plugins:
  modules: List[str]      # Additional plugin modules
  paths: List[str]        # Additional plugin directories

data_sources:
  <source_name>:
    handler: str          # Handler type (csv, json, parquet)
    path: str            # File path
    must_exist: bool     # Whether file must exist
    handler_args: Dict   # Additional handler arguments

plugin_defaults:
  <plugin_name>:
    <param>: Any         # Default parameter values
```

### Case Configuration (cases/*/case.yaml)

```yaml
case_info:
  name: str
  description: str
  version: str

pipeline:
  - plugin: str          # Plugin name
    config: Dict         # Plugin-specific configuration
    outputs:             # Output specifications
      - name: str        # Output name

data_sources:
  <source_name>:
    handler: str
    path: str
    must_exist: bool
    handler_args: Dict

plugins:
  <plugin_name>:
    <param>: Any         # Plugin parameter overrides
```

This API reference provides comprehensive documentation for all public interfaces in the Nexus framework. For implementation details and internal APIs, refer to the source code and architecture documentation.