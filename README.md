# Nexus

A modern data processing framework with simplified architecture featuring case-based workspaces, functional configuration management, and type-safe plugin systems.

## Overview

Nexus is a comprehensive data processing framework that provides:

- **Case-Based Workspaces**: Complete isolated environments for different analysis contexts
- **Simplified Architecture**: Clear separation between cases and templates with copy/reference semantics
- **Type-Safe Plugin System**: Pydantic models with automatic validation
- **Hierarchical Configuration**: CLI > Case > Global > Plugin defaults
- **Functional Configuration Management**: Pure functions with intelligent caching
- **Protocol-Based Data Handlers**: Extensible data I/O with type checking
- **Unified Case Management**: Single case.yaml per case with template support

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nexus.git
cd nexus

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"
```

### Basic Usage

```bash
# List available plugins
nexus list plugins

# List available templates and cases
nexus list templates
nexus list cases

# Run a single plugin with case context
nexus plugin "Data Generator" --case my-analysis --config num_rows=1000

# Single plugin execution with automatic data discovery
# (automatically discovers CSV, JSON, Parquet files in case directory)
nexus plugin "Data Validator" --case analysis-with-data

# Execute case pipeline (uses case.yaml)
nexus run --case my-analysis

# Execute case with template (copy/reference template to case)
nexus run --case my-analysis --template etl-pipeline

# Run with configuration overrides
nexus run --case my-analysis --config plugins.DataGenerator.num_rows=500

# Get help for specific plugin
nexus help --plugin "Data Generator"
```

### Programmatic API

```python
import nexus

# Create engine for specific case
engine = nexus.create_engine(case_path="financial-analysis")

# Run pipeline with template
result = nexus.run_pipeline(
    case_path="financial-analysis",
    template_name="analytics"
)

# Run a single plugin
result = nexus.run_plugin(
    plugin_name="Data Generator",
    case_path="financial-analysis",
    config_overrides={"num_rows": 1000}
)
```

## Core Concepts

### Cases and Templates

Nexus uses a simplified architecture with two key concepts:

#### **Cases** 📁
Complete workspaces for different analysis contexts:

- **Definition**: Each case = data + configuration in one directory
- **Configuration**: One `case.yaml` file per case directory (optional for single plugin execution)
- **Data Path Resolution**: All data paths resolved relative to case directory
- **Isolation**: Each case maintains its own data and configuration context
- **Auto-Discovery**: Automatically discovers data files (CSV, JSON, Parquet, Excel, XML) when no case.yaml exists

#### **Templates** 📄
Reusable pipeline configurations:

- **Global Templates**: Stored in `templates/` directory
- **Built-in Templates**: `default`, `etl-pipeline`, `analytics`, `data-quality`
- **Copy/Reference Logic**: Templates copied to case on first use, referenced thereafter

### Copy/Reference Semantics

Nexus implements intelligent template handling:

1. **Case Execution**: Use existing `case.yaml` in case directory
2. **Template Copy**: Copy template to case directory as `case.yaml` if missing
3. **Template Reference**: Use existing copied template if already present

```bash
# Example: Case with template
nexus run --case financial-analysis --template analytics

# Process:
# 1. Check: cases/financial-analysis/case.yaml exists?
# 2. If missing: Copy templates/analytics.yaml → cases/financial-analysis/case.yaml
# 3. Execute with case.yaml configuration
```

## Available Commands

Nexus provides 4 core commands for simplified workflow:

### 1. `nexus run` - Execute Pipeline

```bash
# Run case pipeline (uses case.yaml)
nexus run --case my-analysis

# Run case with template (copy/reference semantics)
nexus run --case my-analysis --template etl-pipeline

# Run with configuration overrides
nexus run --case my-analysis --config plugins.DataGenerator.num_rows=5000

# Run with multiple config overrides
nexus run --case my-analysis --template analytics \
  --config plugins.DataGenerator.num_rows=10000 \
  --config plugins.DataCleaner.outlier_threshold=3.0

# Verbose logging for debugging
nexus run --case my-analysis --verbose
```

### 2. `nexus plugin` - Execute Single Plugin

```bash
# Run single plugin with case context
nexus plugin "Data Generator" --case my-analysis --config num_rows=1000

# Run plugin with multiple config options
nexus plugin "Data Cleaner" --case my-analysis \
  --config outlier_threshold=2.5 \
  --config missing_strategy=median

# Run plugin with verbose output
nexus plugin "Data Validator" --case my-analysis --verbose
```

### 3. `nexus list` - List Resources

```bash
# List available plugins (default)
nexus list
nexus list plugins

# List available templates
nexus list templates

# List existing cases
nexus list cases
```

### 4. `nexus help` - Get Help

```bash
# General help
nexus help

# Plugin-specific help with configuration options
nexus help --plugin "Data Generator"
nexus help --plugin "Data Cleaner"
```

### Available Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| `default` | Basic data processing pipeline | General data cleaning and validation |
| `etl-pipeline` | Complete ETL workflow | Data extraction, transformation, and loading |
| `analytics` | Data analysis with aggregation | Business analytics and reporting |
| `data-quality` | Comprehensive quality assessment | Data quality validation and profiling |

### Case Management

```bash
# Create new case directory (manual)
mkdir -p cases/my-project/data

# Run creates case directory automatically if missing
nexus run --case my-project --template default

# Cases can use relative or absolute paths
nexus run --case financial-analysis          # Relative to cases_root
nexus run --case /path/to/analysis           # Absolute path
```

### Directory Structure

```
nexus/
├── templates/                    # Global pipeline templates
│   ├── default.yaml             # Basic processing pipeline
│   ├── etl-pipeline.yaml        # Complete ETL workflow
│   ├── analytics.yaml           # Data analysis pipeline
│   └── data-quality.yaml        # Quality assessment pipeline
├── cases/                       # Case workspaces (complete environments)
│   ├── default/                 # Default case workspace
│   │   ├── data/               # Input/output data files
│   │   └── case.yaml           # Pipeline configuration
│   ├── financial-analysis/     # Financial analysis workspace
│   │   ├── data/               # Financial data files
│   │   └── case.yaml           # Analytics pipeline configuration
│   └── data-quality-check/     # Data quality workspace
│       ├── data/               # Data to validate
│       └── case.yaml           # Quality assessment pipeline
├── config/
│   └── global.yaml             # Global configuration (includes cases_root)
├── docs/                       # Documentation
│   └── configuration-best-practices.md
└── src/nexus/                  # Framework source code
    ├── core/                   # Core framework components
    │   ├── case_manager.py     # Case and template management
    │   ├── config.py          # Configuration hierarchy management
    │   ├── context.py         # Immutable contexts
    │   ├── datahub.py         # Data management
    │   ├── discovery.py       # Plugin discovery
    │   ├── engine.py          # Simplified pipeline execution
    │   ├── handlers.py        # Data I/O handlers
    │   └── types.py           # Core type definitions
    ├── plugins/               # Built-in plugins
    │   ├── generators.py      # Data generation plugins
    │   ├── processors.py      # Data processing plugins
    │   └── validators.py      # Data validation plugins
    ├── cli.py                 # Simplified CLI interface
    ├── main.py                # Programmatic API
    └── __init__.py           # Package exports
```

### Built-in Plugins

1. **Data Generator**: Creates synthetic datasets with configurable characteristics
2. **Data Cleaner**: Handles outliers and missing values with multiple strategies
3. **Data Transformer**: Applies normalization, log transforms, and feature engineering
4. **Data Validator**: Validates datasets against quality criteria
5. **Data Quality Checker**: Comprehensive quality assessment with scoring
6. **Data Aggregator**: Groups and aggregates data by specified columns
7. **Sample Data Generator**: Creates predefined sample datasets

### Core Architecture

- **PipelineEngine**: Simplified orchestration with case-based data path resolution
- **CaseManager**: Unified case and template management with copy/reference semantics
- **DataHub**: Centralized data management with lazy loading
- **Plugin Discovery**: Automatic registration and dependency resolution
- **Configuration System**: Hierarchical merging with type validation
- **Handler System**: Protocol-based data I/O (CSV, JSON, Parquet)

## Configuration

### Global Configuration (`config/global.yaml`)

```yaml
framework:
  name: "nexus"
  cases_root: "cases"  # Cases root directory, supports relative and absolute paths
  logging:
    level: INFO

plugins:
  modules: []  # Additional plugin modules
  paths: []    # Additional plugin directories

plugin_defaults:
  "Data Generator":
    num_rows: 1000
    random_seed: 42
```

### Case Configuration (`cases/my-analysis/case.yaml`)

```yaml
case_info:
  name: "Data Processing Pipeline"
  description: "Complete data processing workflow"

pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 1000
    outputs:
      - name: "generated_data"

  - plugin: "Data Cleaner"
    outputs:
      - name: "cleaned_data"

data_sources:
  generated_data:
    handler: "csv"
    path: "data/generated_data.csv"
    must_exist: false
```

## Plugin Development

### Creating a Plugin

```python
from typing import Annotated
import pandas as pd
from nexus import plugin, PluginConfig, DataSource, DataSink

class MyPluginConfig(PluginConfig):
    """Configuration for my custom plugin."""

    input_data: Annotated[pd.DataFrame, DataSource(name="raw_data")]
    threshold: float = 0.5
    output_path: Annotated[str, DataSink(name="processed_data")] = "result.csv"

@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(config: MyPluginConfig, logger) -> pd.DataFrame:
    """Process data with custom logic."""
    logger.info(f"Processing with threshold: {config.threshold}")

    # Your processing logic here
    result = config.input_data.copy()
    result["processed"] = result["value"] > config.threshold

    return result
```

### Plugin Features

- **Automatic Discovery**: Plugins are automatically discovered and registered
- **Type Safety**: Full type hints with Pydantic validation
- **Data Dependencies**: Declarative data source and sink annotations
- **Configuration**: Hierarchical configuration with defaults and overrides
- **Dependency Injection**: Automatic injection of config, logger, context

## Project Structure

```
nexus/
├── src/nexus/
│   ├── core/                 # Core framework components
│   │   ├── config.py        # Functional configuration management
│   │   ├── context.py       # Immutable contexts
│   │   ├── datahub.py       # Data management
│   │   ├── discovery.py     # Plugin discovery
│   │   ├── engine.py        # Pipeline execution
│   │   ├── handlers.py      # Data I/O handlers
│   │   └── types.py         # Core type definitions
│   ├── plugins/             # Built-in plugins
│   │   ├── generators.py    # Data generation plugins
│   │   ├── processors.py    # Data processing plugins
│   │   └── validators.py    # Data validation plugins
│   ├── cli.py              # Command-line interface
│   ├── main.py             # Programmatic API
│   └── __init__.py         # Package exports
├── cases/
│   └── default/            # Default case configuration
│       ├── case.yaml       # Pipeline definition
│       ├── data/           # Data files
│       └── reports/        # Output reports
├── config/
│   └── global.yaml         # Global configuration
├── tests/                  # Test suite
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
└── README.md              # This file
```

## Advanced Usage

### Custom Data Handlers

```python
from nexus.core.types import DataHandler

class MyCustomHandler:
    """Custom data handler for specialized formats."""

    @property
    def produced_type(self) -> type:
        return dict

    def load(self, path: Path) -> dict:
        # Custom loading logic
        pass

    def save(self, data: dict, path: Path) -> None:
        # Custom saving logic
        pass
```

### Configuration Overrides

```bash
# Override nested configuration (no spaces needed in key names)
nexus run --case my-analysis \
  --config plugins.DataGenerator.num_rows=500 \
  --config plugins.DataCleaner.outlier_threshold=2.0

# Multiple overrides for single plugin
nexus plugin "Data Generator" --case my-analysis \
  --config num_rows=1000 \
  --config num_categories=3 \
  --config random_seed=123
```

### Pipeline Composition

```yaml
pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 10000
      num_categories: 5
    outputs:
      - name: "raw_data"

  - plugin: "Data Validator"
    config:
      min_rows: 5000
      required_columns: ["id", "category", "value"]
    outputs:
      - name: "validation_report"

  - plugin: "Data Cleaner"
    config:
      outlier_threshold: 2.5
    outputs:
      - name: "cleaned_data"

  - plugin: "Data Transformer"
    config:
      normalize_columns: ["value", "score"]
      create_derived_features: true
    outputs:
      - name: "transformed_data"
```

## Development

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/nexus --cov-report=html

# Run specific test file
pytest tests/test_nexus_framework.py -v
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Examples

### Data Processing Workflow

```python
import nexus

# Create engine with specific case
engine = nexus.create_engine(case_path="my_analysis")

# Generate synthetic data
data = nexus.run_plugin(
    plugin_name="Data Generator",
    case_path="my_analysis",
    config_overrides={
        "num_rows": 5000,
        "num_categories": 3,
        "noise_level": 0.2
    }
)

# Run complete pipeline
nexus.run_pipeline(
    case_path="my_analysis",
    config_overrides={
        "plugins": {
            "Data Generator": {"num_rows": 5000},
            "Data Cleaner": {"missing_strategy": "median"}
        }
    }
)
```

### Custom Analysis Pipeline

```python
from pathlib import Path
import nexus

# Define case path
case_path = "financial_analysis"

# Execute pipeline with specific configuration
engine = nexus.create_engine(case_path=case_path)

# Run individual steps
raw_data = nexus.run_plugin(
    plugin_name="Sample Data Generator",
    case_path=case_path,
    config_overrides={
        "dataset_type": "sales",
        "size": "large"
    }
)

validation = nexus.run_plugin(
    plugin_name="Data Validator",
    case_path=case_path,
    config_overrides={
        "required_columns": ["sale_id", "amount", "date"],
        "min_rows": 1000
    }
)

quality_report = nexus.run_plugin(
    plugin_name="Data Quality Checker",
    case_path=case_path,
    config_overrides={
        "check_duplicates": True,
        "check_outliers": True,
        "outlier_threshold": 3.0
    }
)
```

## Design Principles

Nexus follows data_replay's functional programming principles:

1. **Immutability**: All contexts are immutable dataclasses
2. **Pure Functions**: Configuration functions have no side effects
3. **Dependency Injection**: Clean separation of concerns
4. **Type Safety**: Comprehensive type hints and validation
5. **Modularity**: Loosely coupled, highly cohesive components
6. **Extensibility**: Plugin-based architecture for easy expansion

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Run the test suite (`pytest`)
6. Run code quality checks (`pre-commit run --all-files`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by the data_replay project's functional programming approach
- Built following Vibecode best practices for clean, maintainable code
- Implements modern Python patterns for type safety and developer experience
