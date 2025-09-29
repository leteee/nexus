# Nexus

A modern data processing framework inspired by data_replay, implementing functional programming patterns with immutable contexts, type-safe plugin systems, and hierarchical configuration management.

## Overview

Nexus is a comprehensive data processing framework that provides:

- **Functional Configuration Management**: Pure functions with intelligent caching
- **Immutable Contexts**: Dataclass-based contexts preventing accidental mutations
- **Type-Safe Plugin System**: Pydantic models with automatic validation
- **Dependency Injection**: Clean plugin execution with auto-discovery
- **Hierarchical Configuration**: CLI > Case > Global > Plugin defaults
- **Protocol-Based Data Handlers**: Extensible data I/O with type checking

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
nexus list

# Run a single plugin
nexus plugin "Data Generator" --config num_rows=1000

# Execute a complete pipeline
nexus run

# Run with configuration overrides
nexus run --config plugins.Data\ Generator.num_rows=500
```

### Programmatic API

```python
import nexus

# Create engine
engine = nexus.create_engine()

# Run a plugin
result = nexus.run_plugin("Data Generator", {"num_rows": 1000})

# Execute pipeline
nexus.run_pipeline()
```

## Features

### Built-in Plugins

1. **Data Generator**: Creates synthetic datasets with configurable characteristics
2. **Data Cleaner**: Handles outliers and missing values with multiple strategies
3. **Data Transformer**: Applies normalization, log transforms, and feature engineering
4. **Data Validator**: Validates datasets against quality criteria
5. **Data Quality Checker**: Comprehensive quality assessment with scoring
6. **Data Aggregator**: Groups and aggregates data by specified columns
7. **Sample Data Generator**: Creates predefined sample datasets

### Core Architecture

- **PipelineEngine**: Orchestrates complete pipeline lifecycle
- **DataHub**: Centralized data management with lazy loading
- **Plugin Discovery**: Automatic registration and dependency resolution
- **Configuration System**: Hierarchical merging with type validation
- **Handler System**: Protocol-based data I/O (CSV, JSON, Parquet)

## Configuration

### Global Configuration (`config/global.yaml`)

```yaml
framework:
  name: "nexus"
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

### Case Configuration (`cases/default/case.yaml`)

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
# Override nested configuration
nexus run --config plugins.Data\ Generator.num_rows=500 \
                  plugins.Data\ Cleaner.outlier_threshold=2.0

# Multiple overrides
nexus plugin "Data Generator" \
  --config num_rows=1000 \
           num_categories=3 \
           random_seed=123
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

# Create engine with custom case
engine = nexus.create_engine(
    case_path="cases/my_analysis"
)

# Generate synthetic data
data = nexus.run_plugin("Data Generator", {
    "num_rows": 5000,
    "num_categories": 3,
    "noise_level": 0.2
})

# Run complete pipeline
nexus.run_pipeline(
    case_path="cases/my_analysis",
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

# Define custom case
case_path = Path("cases/financial_analysis")

# Execute pipeline with specific configuration
engine = nexus.create_engine(case_path=case_path)

# Run individual steps
raw_data = engine.run_plugin("Sample Data Generator", {
    "dataset_type": "sales",
    "size": "large"
})

validation = engine.run_plugin("Data Validator", {
    "required_columns": ["sale_id", "amount", "date"],
    "min_rows": 1000
})

quality_report = engine.run_plugin("Data Quality Checker", {
    "check_duplicates": True,
    "check_outliers": True,
    "outlier_threshold": 3.0
})
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