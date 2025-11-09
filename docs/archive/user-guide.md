# Nexus User Guide

Complete guide to using the Nexus data processing framework.

---

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd nexus

# Install dependencies
pip install -e .
```

### Your First Pipeline

```bash
# Run the quickstart example
nexus run --case quickstart

# Run the comprehensive demo
nexus run --case demo
```

---

## CLI Commands

### `nexus run`

Execute a complete pipeline defined in `case.yaml`.

**Synopsis**:
```bash
nexus run --case CASE [--template TEMPLATE] [--config KEY=VALUE] [--verbose]
```

**Options**:
- `--case`, `-c` (required) - Case directory (relative or absolute)
- `--template`, `-t` - Template to use (replaces case.yaml)
- `--config`, `-C` - Config overrides (repeatable)
- `--verbose`, `-v` - Enable debug logging

**Examples**:
```bash
# Run existing case
nexus run --case quickstart

# Run with template
nexus run --case my-analysis --template etl-pipeline

# Run with config overrides
nexus run -c demo -C plugins.DataGenerator.num_rows=5000

# Run with absolute path
nexus run --case /path/to/case
```

---

### `nexus plugin`

Execute a single plugin with automatic data discovery.

**Synopsis**:
```bash
nexus plugin PLUGIN_NAME --case CASE [--config KEY=VALUE]
```

**Options**:
- `PLUGIN_NAME` (required) - Plugin name (quote if contains spaces)
- `--case`, `-c` (required) - Case directory for data context
- `--config`, `-C` - Config overrides (repeatable)
- `--verbose`, `-v` - Enable debug logging

**Smart Data Discovery**:
- If `case.yaml` exists: Uses defined data sources
- If no `case.yaml`: Auto-discovers CSV, JSON, Parquet, Excel, XML files
- Creates case directory if missing

**Examples**:
```bash
# Run plugin with auto-discovery
nexus plugin "Data Generator" --case my-data

# Run with config overrides
nexus plugin "Data Generator" -c test \
  -C num_rows=1000 \
  -C output_data=data/test.csv

# Run on existing data (auto-discovers files)
nexus plugin "Data Validator" --case /path/to/data
```

---

### `nexus list`

List available resources.

**Synopsis**:
```bash
nexus list [plugins|templates|cases|handlers]
```

**Examples**:
```bash
# List plugins (default)
nexus list
nexus list plugins

# List templates
nexus list templates

# List cases
nexus list cases

# List handlers
nexus list handlers
```

---

### `nexus doc`

Generate API documentation for plugins and handlers.

**Synopsis**:
```bash
nexus doc [--output DIR] [--format FORMAT] [--force]
```

**Options**:
- `--output` - Output directory (default: `docs/api`)
- `--format` - Format: `markdown`, `rst`, or `json` (default: `markdown`)
- `--force`, `-f` - Overwrite without confirmation

**Examples**:
```bash
# Generate all documentation
nexus doc

# Force overwrite
nexus doc --force

# Custom output directory
nexus doc --output docs/reference

# Different format
nexus doc --format rst
```

---

### `nexus help`

Show detailed help information.

**Synopsis**:
```bash
nexus help [--plugin PLUGIN_NAME]
```

**Examples**:
```bash
# General help
nexus help

# Plugin-specific help
nexus help --plugin "Data Generator"
```

---

## Configuration System

### Configuration Hierarchy

**Precedence** (highest to lowest):

```
CLI Overrides → Case/Template Config → Global Config → Plugin Defaults
```

**Note**: Case and Template are **mutually exclusive**:
- With `--template`: Use template (ignores case.yaml)
- Without `--template`: Use case.yaml (must exist)

### Configuration Overrides

**Syntax**:
```bash
--config key=value
-C key=value
```

**Supported Types**:
- Integer: `num_rows=1000` → `1000`
- Float: `threshold=0.95` → `0.95`
- Boolean: `enabled=true` → `True`
- String: `name=test` → `"test"`
- JSON: `config='{"key": "value"}'`

**Nested Keys** (dot notation):
```bash
--config plugins.DataGenerator.num_rows=5000
--config framework.logging.level=DEBUG
```

**Valid Namespaces**:
- `framework.*` - Framework settings
- `data_sources.*` - Global data sources
- `plugins.*` - Plugin configuration

**Examples**:
```bash
# Single override
nexus run -c test -C num_rows=5000

# Multiple overrides
nexus run -c test \
  -C plugins.DataGenerator.num_rows=10000 \
  -C plugins.DataGenerator.random_seed=42 \
  -C framework.logging.level=DEBUG
```

---

## Core Features

### 1. Config-Driven I/O

**No manual data loading/saving required!**

The framework automatically:
- ✅ Registers `DataSource` inputs before execution
- ✅ Loads data into `DataHub` on-demand
- ✅ Saves plugin results to `DataSink` outputs
- ✅ Handles multiple input/output formats

**Example Plugin**:
```python
from nexus import plugin, PluginConfig, DataSource, DataSink
from typing import Annotated
import pandas as pd

class MyPluginConfig(PluginConfig):
    # Input (auto-loaded)
    input_data: Annotated[str, DataSource(handler="csv")] = "data/input.csv"

    # Output (auto-saved)
    output_data: Annotated[str, DataSink(handler="parquet")] = "data/output.parquet"

    # Behavior config
    threshold: float = 0.95

@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(ctx) -> pd.DataFrame:
    # Data already loaded!
    df = ctx.datahub.get("input_data")

    # Process data
    result = df[df['score'] > ctx.config.threshold]

    # Just return - framework saves automatically!
    return result
```

**YAML Usage**:
```yaml
pipeline:
  - plugin: "My Plugin"
    config:
      input_data: "raw/sales.csv"
      output_data: "processed/sales_clean.parquet"
      threshold: 0.8
```

---

### 2. Plugin System

**Plugin Context** (provided to every plugin):
```python
@dataclass(frozen=True)
class PluginContext:
    datahub: DataHub        # Data access
    logger: Logger          # Logging
    project_root: Path      # Project root
    case_path: Path         # Case directory
    config: PluginConfig    # Plugin configuration
```

**Usage**:
```python
@plugin(name="My Plugin", config=MyConfig)
def my_plugin(ctx: PluginContext):
    # Access config
    threshold = ctx.config.threshold

    # Load data
    df = ctx.datahub.get("input_data")

    # Log
    ctx.logger.info(f"Processing {len(df)} rows")

    # Access paths
    output_path = ctx.case_path / "results"

    return processed_df
```

---

### 3. Data Handlers

**Built-in Handlers**:
- `csv` - CSV files (pandas)
- `json` - JSON files
- `parquet` - Parquet files
- `pickle` - Python pickle files
- `data` - Generic pandas DataFrames

**Automatic Handler Selection**:
File extensions automatically map to handlers:
- `.csv` → `csv` handler
- `.json` → `json` handler
- `.parquet` → `parquet` handler
- `.pkl` → `pickle` handler

**DataSource with Handler Args**:
```python
input_data: Annotated[str, DataSource(
    handler="csv",
    handler_args={
        "sep": ";",
        "encoding": "utf-8"
    }
)] = "data/input.csv"
```

---

### 4. Type Safety

**Pydantic models** for configuration:
```python
class MyConfig(PluginConfig):
    num_rows: int = 1000       # Type-checked
    threshold: float = 0.95    # Type-checked
    enabled: bool = True       # Type-checked
```

**Type hints** for plugin functions:
```python
def my_plugin(ctx: PluginContext) -> pd.DataFrame:
    ...
```

---

## Pipeline Definition

### Basic Pipeline

```yaml
# case.yaml
case_info:
  name: "My Pipeline"
  description: "Multi-step data processing"
  version: "1.0.0"

pipeline:
  # Step 1: Generate data
  - plugin: "Data Generator"
    config:
      num_rows: 10000
      output_data: "data/01_raw.csv"

  # Step 2: Filter data
  - plugin: "Data Filter"
    config:
      input_data: "data/01_raw.csv"
      output_data: "data/02_filtered.csv"
      column: "value"
      operator: ">"
      threshold: 0.5

  # Step 3: Aggregate data
  - plugin: "Data Aggregator"
    config:
      input_data: "data/02_filtered.csv"
      output_data: "data/03_aggregated.csv"
      group_by: "category"
      agg_column: "value"
      agg_function: "mean"

  # Step 4: Validate results
  - plugin: "Data Validator"
    config:
      input_data: "data/03_aggregated.csv"
      output_report: "reports/validation.json"
```

### Execution Flow

```
1. Load global config (global.yaml)
2. Load case config (case.yaml)
3. Merge configurations (CLI > Case > Global > Defaults)
4. Initialize DataHub
5. For each pipeline step:
   a. Extract I/O metadata from config
   b. Register DataSource inputs
   c. Create plugin context
   d. Execute plugin
   e. Save to DataSink outputs
6. Return results
```

---

## Creating Custom Plugins

### 1. Create Plugin File

`my_plugins.py`:
```python
from nexus import plugin, PluginConfig, DataSource, DataSink
from typing import Annotated
import pandas as pd

class MyPluginConfig(PluginConfig):
    input_data: Annotated[str, DataSource(handler="csv")] = "data/input.csv"
    output_data: Annotated[str, DataSink(handler="parquet")] = "data/output.parquet"
    threshold: float = 0.5

@plugin(name="My Custom Plugin", config=MyPluginConfig)
def my_custom_plugin(ctx) -> pd.DataFrame:
    """
    Custom plugin that filters data based on a threshold.
    """
    df = ctx.datahub.get("input_data")

    ctx.logger.info(f"Processing {len(df)} rows")

    # Custom logic
    result = df[df['score'] > ctx.config.threshold]

    ctx.logger.info(f"Filtered to {len(result)} rows")

    return result
```

### 2. Register in `global.yaml`

```yaml
framework:
  discovery:
    plugins:
      paths:
        - "path/to/my_plugins.py"
```

### 3. Use Your Plugin

```bash
# List plugins (should show your custom plugin)
nexus list plugins

# Run your plugin
nexus plugin "My Custom Plugin" -c test

# Use in pipeline
nexus run --case my-case
```

---

## Tips & Best Practices

### 1. Quick Data Generation

```bash
# Generate test data without case.yaml
nexus plugin "Data Generator" -c temp-data -C num_rows=1000
```

### 2. Reproducible Results

```bash
# Fix random seed for reproducibility
nexus run -c analysis -C plugins.DataGenerator.random_seed=42
```

### 3. Output Format Control

```bash
# Change output format via path extension
nexus plugin "Data Generator" -c test \
  -C output_data=data/output.parquet  # Auto-detects parquet handler
```

### 4. Debugging

```bash
# Enable verbose logging
nexus run -c problematic-case -v

# Save debug log
nexus run -c test -v 2>&1 | tee debug.log
```

### 5. Batch Operations

```bash
# Process multiple cases
for case in exp-{001..010}; do
  nexus run --case $case
done
```

---

## Project Structure

```
nexus/
├── config/
│   └── global.yaml              # Global configuration
├── cases/
│   ├── quickstart/              # Minimal example
│   │   ├── case.yaml
│   │   └── data/
│   └── demo/                    # Comprehensive demo
│       ├── case.yaml
│       ├── data/
│       └── reports/
├── templates/                   # Reusable templates
│   └── *.yaml
├── src/nexus/
│   ├── plugins/                 # Built-in plugins
│   │   ├── generators.py
│   │   └── processors.py
│   └── core/                    # Framework core
└── docs/                        # Documentation
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (missing files, invalid config, etc.) |

---

## See Also

- **[API Documentation](api/README.md)** - Plugin & handler reference with full config examples
  - Run `nexus doc` to generate
  - Includes complete YAML config templates for all plugins
- [Architecture](architecture.md) - Framework internals
- [Execution Flows](execution-flows.md) - Visual flow diagrams
- [Examples](../cases/README.md) - Example cases
