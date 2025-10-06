# CLI Command Reference

Complete reference for all Nexus CLI commands.

---

## Table of Contents

- [Overview](#overview)
- [Global Options](#global-options)
- [Commands](#commands)
  - [nexus run](#nexus-run)
  - [nexus plugin](#nexus-plugin)
  - [nexus list](#nexus-list)
  - [nexus init](#nexus-init)
  - [nexus validate](#nexus-validate)
  - [nexus doc](#nexus-doc)
  - [nexus help](#nexus-help)
- [Configuration Overrides](#configuration-overrides)
- [Examples](#examples)

---

## Overview

Nexus provides a simple, focused CLI for data pipeline execution:

```bash
nexus [OPTIONS] COMMAND [ARGS]...
```

**Philosophy**:
- Clear, single-purpose commands
- Minimal required options
- Smart defaults and auto-discovery
- Configuration via YAML + CLI overrides

---

## Global Options

### `--version`
Show version information and exit.

```bash
nexus --version
# Output: Nexus 0.2.0
```

### `--help`
Show help message and exit.

```bash
nexus --help
```

---

## Commands

### `nexus run`

**Purpose**: Execute a complete pipeline using `case.yaml` configuration.

#### Synopsis
```bash
nexus run --case CASE [OPTIONS]
```

#### Options

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--case` | `-c` | ✅ | Case directory (relative to `cases/` or absolute path) |
| `--template` | `-t` | ❌ | Template name to copy/reference |
| `--config` | `-C` | ❌ | Config overrides in `key=value` format (repeatable) |
| `--verbose` | `-v` | ❌ | Enable verbose logging |

#### Behavior

**With Template**:
- If `case.yaml` missing → Copy template to create it
- If `case.yaml` exists → Reference template for defaults

**Without Template**:
- Requires existing `case.yaml`
- Raises error if not found

#### Examples

```bash
# Run existing case
nexus run --case quickstart

# Run with template (creates case.yaml if missing)
nexus run --case my-analysis --template analytics

# Run with config overrides
nexus run --case quickstart --config num_rows=5000

# Run with multiple overrides
nexus run -c pipeline-flow \
  -C plugins.DataGenerator.num_rows=10000 \
  -C plugins.DataGenerator.random_seed=123

# Run with absolute path
nexus run --case /path/to/custom/case

# Verbose logging
nexus run -c quickstart -v
```

#### Output

- Executes pipeline steps in order
- Auto-registers DataSource inputs
- Auto-saves to DataSink outputs
- Logs progress and results

---

### `nexus plugin`

**Purpose**: Execute a single plugin with automatic data discovery.

#### Synopsis
```bash
nexus plugin PLUGIN_NAME --case CASE [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `PLUGIN_NAME` | ✅ | Name of the plugin to execute (quoted if contains spaces) |

#### Options

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--case` | `-c` | ✅ | Case directory for data context |
| `--config` | `-C` | ❌ | Config overrides in `key=value` format (repeatable) |
| `--verbose` | `-v` | ❌ | Enable verbose logging |

#### Smart Data Discovery

**If `case.yaml` exists**:
- Uses defined `data_sources`
- Auto-discovers additional files in case directory

**If no `case.yaml`**:
- Auto-discovers data files (CSV, JSON, Parquet, Excel, XML)
- Creates minimal case context

**Case directory created if missing**

#### Examples

```bash
# Run plugin with auto-discovery
nexus plugin "Data Generator" --case my-data

# Run with config overrides
nexus plugin "Data Generator" -c test-run \
  -C num_rows=1000 \
  -C output_data=data/test.csv

# Run plugin on existing data directory (auto-discovers files)
nexus plugin "Data Validator" --case /path/to/data

# Run with sample data
nexus plugin "Sample Data Generator" -c samples \
  -C dataset_type=customers \
  -C size=large
```

#### Output

- Executes single plugin
- Auto-saves to DataSink (if defined in plugin config)
- Returns plugin result

---

### `nexus list`

**Purpose**: List available resources (plugins, templates, cases).

#### Synopsis
```bash
nexus list [RESOURCE_TYPE]
```

#### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `RESOURCE_TYPE` | `plugins` | What to list: `plugins`, `templates`, or `cases` |

#### Examples

```bash
# List plugins (default)
nexus list
nexus list plugins

# List templates
nexus list templates

# List cases
nexus list cases
```

#### Output Examples

**Plugins**:
```
Available Plugins:
  - Data Generator
  - Sample Data Generator
```

**Templates**:
```
Available Templates:
  - analytics.yaml
  - data-quality.yaml
  - etl-pipeline.yaml
```

**Cases**:
```
Available Cases:
  quickstart         → D:\Projects\nexus\cases\quickstart
  hybrid-paths       → D:\Projects\nexus\cases\hybrid-paths
  pipeline-flow      → D:\Projects\nexus\cases\pipeline-flow
  multi-output       → D:\Projects\nexus\cases\multi-output
```

---

### `nexus doc`

**Purpose**: Generate comprehensive documentation for plugins.

#### Synopsis
```bash
nexus doc [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--plugin` | TEXT | Generate documentation for specific plugin |
| `--output` | PATH | Output file path (default: stdout) |
| `--format` | CHOICE | Output format: `markdown`, `rst`, or `json` (default: `markdown`) |
| `--all` | FLAG | Generate documentation for all discovered plugins |

#### Features

- **Auto-Discovery**: Automatically discovers and documents all registered plugins
- **Multiple Formats**: Export as Markdown, reStructuredText, or JSON
- **Comprehensive**: Includes configuration, signatures, data sources/sinks
- **Examples**: Auto-generates usage examples for CLI and Python API

#### Examples

```bash
# Document a specific plugin (output to stdout)
nexus doc --plugin "Data Generator"

# Save documentation to file
nexus doc --plugin "Data Generator" --output docs/plugins/generator.md

# Generate documentation for all plugins (separate files)
nexus doc --all --output docs/plugins/

# Generate JSON documentation for API consumption
nexus doc --plugin "My Plugin" --format json --output plugin-spec.json

# Generate reStructuredText for Sphinx
nexus doc --plugin "Data Processor" --format rst --output plugin.rst
```

#### Output Structure (Markdown)

Generated documentation includes:
- **Plugin Name and Description**
- **Overview** (from docstring)
- **Configuration Table** (parameters, types, defaults, descriptions)
- **Function Signature**
- **Data Sources** (required inputs)
- **Data Sinks** (expected outputs)
- **Usage Examples** (CLI and Python API)

Example output:
```markdown
# Data Generator

**Description**: Generate synthetic datasets for testing

## Overview

Generates random data based on configuration parameters...

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_rows` | `int` | 100 | Number of rows to generate |
| `seed` | `int` | *(required)* | Random seed for reproducibility |

## Function Signature

\`\`\`python
def generate_synthetic_data(config: DataGeneratorConfig, logger) -> pd.DataFrame:
    ...
\`\`\`

## Usage Example

### CLI
\`\`\`bash
nexus plugin "Data Generator" --case mycase
nexus plugin "Data Generator" --case mycase --config num_rows=1000
\`\`\`

### Python API
\`\`\`python
from nexus import create_engine

engine = create_engine("mycase")
result = engine.run_single_plugin("Data Generator")
\`\`\`
```

---

### `nexus help`

**Purpose**: Show detailed help information.

#### Synopsis
```bash
nexus help [--plugin PLUGIN_NAME]
```

#### Options

| Option | Description |
|--------|-------------|
| `--plugin` | Show detailed help for specific plugin |

#### Examples

```bash
# General help
nexus help

# Plugin-specific help (future)
nexus help --plugin "Data Generator"
```

---

## Configuration Overrides

### Syntax

```bash
--config key=value
-C key=value
```

### Supported Value Types

| Type | Example | Parsed As |
|------|---------|-----------|
| Integer | `num_rows=1000` | `1000` (int) |
| Float | `threshold=0.95` | `0.95` (float) |
| Boolean | `remove_nulls=true` | `True` (bool) |
| String | `name=test` | `"test"` (str) |

### Nested Keys

Use dot notation for nested configuration:

```bash
# Plugin-specific config
--config plugins.DataGenerator.num_rows=5000

# Deep nesting
--config plugins.DataGenerator.output_data=data/custom.csv
```

### Multiple Overrides

Repeat `-C` flag for multiple overrides:

```bash
nexus run -c test \
  -C num_rows=5000 \
  -C noise_level=0.2 \
  -C output_data=results/data.csv
```

---

## Examples

### Quick Start Examples

```bash
# 1. Run quickstart example
nexus run --case quickstart

# 2. Generate custom data
nexus plugin "Data Generator" --case my-test \
  --config num_rows=10000 \
  --config output_data=data/large_dataset.csv

# 3. List available plugins
nexus list plugins

# 4. List example cases
nexus list cases
```

### Advanced Examples

```bash
# Multi-step pipeline with overrides
nexus run --case pipeline-flow \
  -C plugins.DataGenerator.num_rows=50000 \
  -C plugins.DataGenerator.random_seed=999

# Generate multiple dataset types
nexus plugin "Sample Data Generator" -c sales-data \
  -C dataset_type=sales \
  -C size=large \
  -C output_data=data/sales_2024.csv

nexus plugin "Sample Data Generator" -c customer-data \
  -C dataset_type=customers \
  -C size=medium \
  -C output_data=data/customers.csv

# Run on absolute path
nexus run --case /tmp/data-processing/experiment-001

# Verbose logging for debugging
nexus run -c quickstart -v
```

### Integration Examples

```bash
# In CI/CD pipeline
nexus run --case data-validation \
  --config input_data=/data/incoming/batch_001.csv \
  --config output_report=/reports/validation_001.json

# Batch processing script
for dataset in sales customers products; do
  nexus plugin "Sample Data Generator" \
    --case "batch-$dataset" \
    --config dataset_type=$dataset \
    --config size=large
done

# Development workflow
# 1. Create test case
nexus plugin "Data Generator" -c dev-test -C num_rows=100

# 2. Run pipeline
nexus run -c dev-test

# 3. Check results
ls -lh cases/dev-test/data/
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (missing files, invalid config, etc.) |
| `2` | Plugin execution error |

---

## Environment Variables

### `NEXUS_CASES_ROOT`
Override default cases directory.

```bash
export NEXUS_CASES_ROOT=/custom/cases
nexus run --case my-case  # Looks in /custom/cases/my-case
```

---

## Tips & Tricks

### 1. Quick Data Generation
```bash
# Generate test data without case.yaml
nexus plugin "Data Generator" -c temp-data -C num_rows=1000
```

### 2. Reproducible Results
```bash
# Fix random seed for reproducibility
nexus run -c analysis -C random_seed=42
```

### 3. Output Format Control
```bash
# Change output format via path extension
nexus plugin "Data Generator" -c test \
  -C output_data=data/output.parquet  # Auto-detects parquet handler
```

### 4. Batch Operations
```bash
# Process multiple cases
for case in exp-{001..010}; do
  nexus run --case $case -C random_seed=$RANDOM
done
```

### 5. Debugging
```bash
# Enable verbose logging
nexus run -c problematic-case -v 2>&1 | tee debug.log
```

---

## See Also

- [Feature Guide](features.md) - Complete feature overview
- [Cases README](../cases/README.md) - Example cases
- [Configuration Best Practices](configuration-best-practices.md) - Advanced configuration
- [Architecture](architecture.md) - Framework internals
