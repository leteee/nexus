# Nexus Feature Guide

Complete overview of Nexus framework capabilities and features.

---

## Table of Contents

- [Core Features](#core-features)
- [Configuration System](#configuration-system)
- [Plugin System](#plugin-system)
- [Data Management](#data-management)
- [Path Resolution](#path-resolution)
- [Pipeline Execution](#pipeline-execution)
- [Built-in Plugins](#built-in-plugins)
- [Extensibility](#extensibility)

---

## Core Features

### 1. **Hybrid Path Resolution** ⭐

Nexus supports **three path resolution strategies** for maximum flexibility:

| Strategy | Syntax | Use Case |
|----------|--------|----------|
| **Explicit Logical Name** | `@customer_master` | Reference global data sources (recommended) |
| **Implicit Logical Name** | `customer_master` | Auto-detected if exists in `data_sources` |
| **Direct Path** | `data/file.csv` | Simple file paths |

**Example**:
```yaml
data_sources:
  customer_master:
    handler: "parquet"
    path: "/warehouse/customers.parquet"

pipeline:
  - plugin: "My Plugin"
    config:
      input1: "@customer_master"    # Explicit (recommended)
      input2: "customer_master"     # Implicit (auto-detected)
      input3: "temp/data.csv"       # Direct path
```

---

### 2. **Automatic I/O Handling** 🔄

**No manual data loading/saving required!**

The framework automatically:
- ✅ Registers `DataSource` inputs before plugin execution
- ✅ Loads data into `DataHub` on-demand (lazy loading)
- ✅ Saves plugin results to `DataSink` outputs
- ✅ Handles single and multi-output plugins

**Example**:
```python
from nexus import plugin, PluginConfig, DataSource, DataSink
from typing import Annotated

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

    # Process...
    result = df[df['score'] > ctx.config.threshold]

    # Just return - framework saves automatically!
    return result
```

---

### 3. **Multi-Output Plugins** 📦

Plugins can return multiple outputs by returning a dictionary:

```python
@plugin(name="Train Test Split", config=SplitConfig)
def split_data(ctx) -> Dict[str, pd.DataFrame]:
    df = ctx.datahub.get("input_data")

    train, test, val = train_test_split(df, ...)

    # Return dict with keys matching config DataSink fields
    return {
        "train_data": train,
        "test_data": test,
        "validation_data": val
    }
```

**Config**:
```python
class SplitConfig(PluginConfig):
    input_data: Annotated[str, DataSource(...)] = "data/input.csv"

    # Multiple outputs
    train_data: Annotated[str, DataSink(...)] = "data/train.parquet"
    test_data: Annotated[str, DataSink(...)] = "data/test.parquet"
    validation_data: Annotated[str, DataSink(...)] = "data/val.parquet"
```

---

### 4. **Smart Data Discovery** 🔍

**Single Plugin Execution** automatically discovers data files:

```bash
nexus plugin "Data Validator" --case /path/to/data
```

**Auto-discovers**:
- `.csv` → CSV handler
- `.json` → JSON handler
- `.parquet` → Parquet handler
- `.xlsx` → Excel handler
- `.xml` → XML handler

**No `case.yaml` required!**

---

### 5. **Type Safety** ✅

**Comprehensive type checking**:

```python
# Pydantic models for config
class MyConfig(PluginConfig):
    num_rows: int = 1000          # Type-checked
    threshold: float = 0.95       # Type-checked
    enabled: bool = True          # Type-checked

# Type hints everywhere
def my_plugin(ctx: PluginContext) -> pd.DataFrame:
    ...

# DataSource schema validation
input_data: Annotated[str, DataSource(
    handler="csv",
    schema=pd.DataFrame  # Validates loaded data type
)]
```

---

## Configuration System

### Hierarchical Configuration

**Precedence** (highest to lowest):

```
CLI Overrides  →  case.yaml  →  global.yaml  →  Plugin Defaults
```

**Example**:
```yaml
# global.yaml
plugins:
  "Data Generator":
    random_seed: 42

# case.yaml
plugins:
  "Data Generator":
    num_rows: 5000        # Overrides default

# CLI
--config num_rows=10000   # Overrides case.yaml
```

---

### Configuration in Plugin Config

**All configuration in one place**:

```python
class DataCleanerConfig(PluginConfig):
    # I/O Configuration
    input_data: Annotated[str, DataSource(handler="csv")] = "data/raw.csv"
    output_data: Annotated[str, DataSink(handler="parquet")] = "data/clean.parquet"

    # Behavior Configuration
    remove_nulls: bool = True
    fill_strategy: str = "mean"
    outlier_threshold: float = 2.5
```

**YAML Usage**:
```yaml
pipeline:
  - plugin: "Data Cleaner"
    config:
      # Override I/O
      input_data: "raw/sales.csv"
      output_data: "processed/sales_clean.parquet"

      # Override behavior
      remove_nulls: false
      fill_strategy: "median"
```

---

### Global Data Sources

**Define once, use everywhere**:

```yaml
# case.yaml
data_sources:
  # Reusable data sources
  customer_master:
    handler: "parquet"
    path: "/warehouse/dim_customers.parquet"

  product_catalog:
    handler: "csv"
    path: "/warehouse/dim_products.csv"

pipeline:
  - plugin: "Data Enricher"
    config:
      customers: "@customer_master"    # Reference
      products: "@product_catalog"     # Reference
      output: "enriched/combined.parquet"
```

---

## Plugin System

### Plugin Registration

**Decorator-based**:
```python
from nexus import plugin, PluginConfig

@plugin(name="My Plugin", config=MyConfig)
def my_plugin(ctx: PluginContext):
    # Plugin logic
    pass
```

**Auto-discovery**:
- Plugins in `src/nexus/plugins/`
- Custom plugin directories via `global.yaml`

---

### Plugin Context

**Immutable context provided to every plugin**:

```python
@dataclass(frozen=True)
class PluginContext:
    datahub: DataHub           # Data access
    logger: Logger             # Logging
    project_root: Path         # Project root
    case_path: Path            # Case directory
    config: PluginConfig       # Plugin configuration
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

## Data Management

### DataHub

**Central data registry with**:
- ✅ Lazy loading
- ✅ Automatic caching
- ✅ Type validation
- ✅ Multiple handler support

**Handlers**:
- `csv` - CSV files (pandas)
- `json` - JSON files
- `parquet` - Parquet files
- `pickle` - Python pickle
- Custom handlers (extensible)

---

### DataSource Annotation

```python
from typing import Annotated
from nexus import DataSource

input_data: Annotated[str, DataSource(
    handler="csv",           # Data format
    required=True,           # Must exist
    schema=pd.DataFrame,     # Type validation
    handler_args={           # Custom args
        "sep": ";",
        "encoding": "utf-8"
    }
)] = "data/input.csv"
```

---

### DataSink Annotation

```python
from typing import Annotated
from nexus import DataSink

output_data: Annotated[str, DataSink(
    handler="parquet",       # Output format
    schema=pd.DataFrame,     # Type hint
    handler_args={           # Custom args
        "compression": "snappy"
    }
)] = "data/output.parquet"
```

---

## Path Resolution

### Resolution Logic

```python
def resolve_path(value: str) -> str:
    # 1. Explicit logical name (@prefix)
    if value.startswith("@"):
        return data_sources[value[1:]]["path"]

    # 2. Implicit logical name (identifier + exists)
    if is_identifier(value) and value in data_sources:
        return data_sources[value]["path"]

    # 3. Direct path
    return value
```

### Naming Rules

**Valid Logical Names** (implicit):
- ✅ `customer_master`
- ✅ `product_v2`
- ✅ `staging_data`
- ✅ `_internal_cache`

**Requires @ Prefix** (explicit):
- ⚠️ `@2024-sales` (contains `-`)
- ⚠️ `@data.csv` (contains `.`)
- ⚠️ `@raw/data` (contains `/`)

---

## Pipeline Execution

### Pipeline Definition

```yaml
pipeline:
  # Step 1
  - plugin: "Data Generator"
    config:
      num_rows: 5000
      output_data: "step1/generated.csv"

  # Step 2
  - plugin: "Data Cleaner"
    config:
      input_data: "step1/generated.csv"
      output_data: "step2/cleaned.parquet"

  # Step 3
  - plugin: "Data Validator"
    config:
      input_data: "step2/cleaned.parquet"
      output_report: "reports/validation.json"
```

### Execution Flow

```
1. Load global config
2. Load case config
3. Merge configurations
4. Initialize DataHub
5. Register global data sources
6. For each step:
   a. Extract I/O metadata from config
   b. Register DataSource inputs
   c. Create plugin context
   d. Execute plugin
   e. Save to DataSink outputs
7. Return results
```

---

## Built-in Plugins

### Data Generator

**Purpose**: Generate synthetic test data

**Config**:
```python
class DataGeneratorConfig(PluginConfig):
    output_data: Annotated[str, DataSink(handler="csv")] = "data/generated.csv"
    num_rows: int = 1000
    num_categories: int = 5
    noise_level: float = 0.1
    random_seed: int = 42
```

**Usage**:
```bash
nexus plugin "Data Generator" -c test \
  -C num_rows=10000 \
  -C output_data=data/large_dataset.csv
```

---

### Sample Data Generator

**Purpose**: Generate predefined sample datasets

**Config**:
```python
class SampleDataGeneratorConfig(PluginConfig):
    output_data: Annotated[str, DataSink(handler="csv")] = "data/sample.csv"
    dataset_type: str = "sales"  # sales, customers, products
    size: str = "small"          # small, medium, large
```

**Datasets**:
- `sales` - Sales transactions (product, region, amount, date, ...)
- `customers` - Customer records (name, age, city, premium, ...)
- `products` - Product catalog (name, category, price, stock, ...)

**Usage**:
```bash
nexus plugin "Sample Data Generator" -c samples \
  -C dataset_type=customers \
  -C size=large \
  -C output_data=data/customers_10k.csv
```

---

## Extensibility

### Custom Plugins

**1. Create plugin file**: `my_plugins.py`

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
    df = ctx.datahub.get("input_data")

    # Custom logic
    result = df[df['score'] > ctx.config.threshold]

    return result
```

**2. Register in `global.yaml`**:

```yaml
plugins:
  paths:
    - "path/to/my_plugins.py"
```

**3. Use**:
```bash
nexus plugin "My Custom Plugin" -c test
```

---

### Custom Data Handlers

```python
from pathlib import Path
import pandas as pd

class CustomHandler:
    @property
    def produced_type(self) -> type:
        return pd.DataFrame

    def load(self, path: Path) -> pd.DataFrame:
        # Custom loading logic
        return pd.read_custom(path)

    def save(self, data: pd.DataFrame, path: Path) -> None:
        # Custom saving logic
        data.to_custom(path)

# Register
from nexus.core.handlers import register_handler
register_handler("custom", CustomHandler())
```

---

## Feature Matrix

| Feature | Status | Description |
|---------|--------|-------------|
| **Hybrid Path Resolution** | ✅ | @prefix, implicit, direct paths |
| **Auto I/O Handling** | ✅ | DataSource/DataSink automation |
| **Multi-Output Plugins** | ✅ | Dict return for multiple outputs |
| **Smart Discovery** | ✅ | Auto-detect data files |
| **Type Safety** | ✅ | Pydantic + type hints |
| **Hierarchical Config** | ✅ | CLI → Case → Global → Default |
| **Lazy Loading** | ✅ | On-demand data loading |
| **Caching** | ✅ | Automatic data caching |
| **Plugin Auto-Discovery** | ✅ | Decorator-based registration |
| **Custom Handlers** | ✅ | Extensible I/O system |
| **Pipeline Execution** | ✅ | Multi-step orchestration |
| **Single Plugin Execution** | ✅ | Standalone plugin runs |
| **Global Data Sources** | ✅ | Reusable data registry |
| **Configuration Overrides** | ✅ | CLI config overrides |

---

## Quick Reference Card

### Path Resolution
```yaml
"@name"         # Explicit (recommended)
"name"          # Implicit (auto-detected)
"path/file"     # Direct path
```

### Plugin Config Structure
```python
class MyConfig(PluginConfig):
    # I/O
    input: Annotated[str, DataSource(...)] = "..."
    output: Annotated[str, DataSink(...)] = "..."

    # Behavior
    param: type = default
```

### Pipeline Pattern
```yaml
data_sources:
  logical_name:
    handler: "type"
    path: "/path"

pipeline:
  - plugin: "Name"
    config:
      input: "@logical_name"
      output: "path/out"
      param: value
```

### CLI Commands
```bash
nexus run -c case [-C key=value]
nexus plugin "Name" -c case [-C key=value]
nexus list [plugins|cases|templates]
```

---

## See Also

- [CLI Reference](cli-reference.md) - Complete CLI documentation
- [Cases README](../cases/README.md) - Example cases
- [Architecture](architecture.md) - Framework internals
- [Configuration Best Practices](configuration-best-practices.md) - Advanced patterns
