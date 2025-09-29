# Plugin Development Guide

This guide covers everything you need to know about developing plugins for the Nexus framework.

## Quick Start

### Basic Plugin Structure

```python
from typing import Annotated
import pandas as pd
from nexus import plugin, PluginConfig, DataSource, DataSink

class MyPluginConfig(PluginConfig):
    """Configuration for my plugin."""

    # Input data source
    input_data: Annotated[pd.DataFrame, DataSource(name="raw_data")]

    # Configuration parameters
    threshold: float = 0.5
    process_mode: str = "standard"

    # Output data sink
    output_path: Annotated[str, DataSink(name="processed_data")] = "result.csv"

@plugin(name="My Plugin", config=MyPluginConfig)
def my_plugin(config: MyPluginConfig, logger) -> pd.DataFrame:
    """
    Process data according to configuration.

    Args:
        config: Plugin configuration with data and parameters
        logger: Logger instance for output

    Returns:
        Processed DataFrame
    """
    logger.info(f"Processing {len(config.input_data)} rows with threshold {config.threshold}")

    # Your processing logic here
    result = config.input_data.copy()
    result["processed"] = result["value"] > config.threshold

    logger.info(f"Processing complete: {result['processed'].sum()} rows passed threshold")
    return result
```

### Plugin Registration

Plugins are automatically discovered and registered when imported. The `@plugin` decorator handles:

- Registration in the global plugin registry
- Configuration model binding
- Metadata association
- Auto-discovery of data dependencies

## Configuration System

### Plugin Configuration Classes

All plugins should define a configuration class inheriting from `PluginConfig`:

```python
from nexus import PluginConfig
from typing import Annotated, Optional, List, Dict, Any

class AdvancedPluginConfig(PluginConfig):
    """Advanced plugin configuration example."""

    # Required data sources
    input_data: Annotated[pd.DataFrame, DataSource(name="source_data")]
    reference_data: Annotated[pd.DataFrame, DataSource(name="reference")]

    # Optional data sources (with defaults)
    metadata: Annotated[Optional[Dict], DataSource(name="metadata")] = None

    # Configuration parameters with validation
    threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    categories: List[str] = ["A", "B", "C"]

    # Advanced configuration
    processing_options: Dict[str, Any] = {
        "remove_duplicates": True,
        "normalize": False,
        "outlier_method": "iqr"
    }

    # Output configuration
    output_path: Annotated[str, DataSink(name="result")] = "output.csv"
    report_path: Annotated[str, DataSink(name="report")] = "report.json"
```

### Configuration Features

#### 1. Type Validation

Pydantic automatically validates configuration types:

```python
class ValidatedConfig(PluginConfig):
    # Numeric constraints
    count: Annotated[int, Field(ge=1, le=10000)] = 100

    # String patterns
    mode: Annotated[str, Field(pattern=r"^(fast|standard|thorough)$")] = "standard"

    # Custom validation
    @field_validator('custom_field')
    def validate_custom(cls, v):
        if v < 0:
            raise ValueError("Must be positive")
        return v
```

#### 2. Default Values

Provide sensible defaults for all optional parameters:

```python
class DefaultsConfig(PluginConfig):
    # Required (no default)
    input_data: Annotated[pd.DataFrame, DataSource(name="data")]

    # Optional with defaults
    threshold: float = 0.5
    method: str = "linear"
    iterations: int = 100

    # Complex defaults
    options: Dict[str, str] = field(default_factory=lambda: {"mode": "auto"})
```

#### 3. Data Source Annotations

Declare data dependencies using typed annotations:

```python
class DataConfig(PluginConfig):
    # Standard data source
    primary_data: Annotated[pd.DataFrame, DataSource(name="primary")]

    # Data source with handler options
    secondary_data: Annotated[
        pd.DataFrame,
        DataSource(name="secondary", handler_args={"sep": ";", "encoding": "utf-8"})
    ]

    # Optional data source
    optional_data: Annotated[
        Optional[pd.DataFrame],
        DataSource(name="optional")
    ] = None

    # Data sink for output
    output: Annotated[str, DataSink(name="output")] = "result.parquet"
```

## Plugin Function Patterns

### 1. Data Processing Plugin

```python
@plugin(name="Data Processor", config=ProcessorConfig)
def process_data(config: ProcessorConfig, logger) -> pd.DataFrame:
    """Standard data processing plugin."""

    logger.info(f"Processing {len(config.input_data)} rows")

    # Data processing logic
    df = config.input_data.copy()

    # Apply transformations
    if config.normalize:
        df = normalize_data(df)

    if config.remove_outliers:
        df = remove_outliers(df, config.outlier_threshold)

    logger.info(f"Processing complete: {len(df)} rows remaining")
    return df
```

### 2. Analysis Plugin

```python
@plugin(name="Data Analyzer", config=AnalyzerConfig)
def analyze_data(config: AnalyzerConfig, logger) -> Dict[str, Any]:
    """Analysis plugin returning structured results."""

    logger.info("Starting data analysis")

    df = config.input_data

    # Perform analysis
    analysis_results = {
        "summary_stats": df.describe().to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "data_types": df.dtypes.to_dict(),
        "correlations": df.corr().to_dict() if df.select_dtypes(include=[np.number]).shape[1] > 1 else {}
    }

    logger.info("Analysis complete")
    return analysis_results
```

### 3. Validation Plugin

```python
@plugin(name="Data Validator", config=ValidatorConfig)
def validate_data(config: ValidatorConfig, logger) -> Dict[str, Any]:
    """Data validation plugin with detailed reporting."""

    df = config.input_data
    issues = []

    # Check required columns
    missing_cols = set(config.required_columns) - set(df.columns)
    if missing_cols:
        issues.append(f"Missing columns: {list(missing_cols)}")

    # Check data quality
    null_pct = (df.isnull().sum() / len(df)) * 100
    high_null_cols = null_pct[null_pct > config.max_null_percentage].index.tolist()
    if high_null_cols:
        issues.append(f"High null percentage in: {high_null_cols}")

    # Generate report
    report = {
        "status": "PASSED" if not issues else "FAILED",
        "issues": issues,
        "metrics": {
            "row_count": len(df),
            "column_count": len(df.columns),
            "null_percentage": float(null_pct.mean())
        }
    }

    logger.info(f"Validation {report['status']}: {len(issues)} issues found")
    return report
```

### 4. Multi-Output Plugin

```python
@plugin(name="Multi Output Processor", config=MultiOutputConfig)
def process_multi_output(config: MultiOutputConfig, logger, datahub) -> None:
    """Plugin that saves multiple outputs directly."""

    df = config.input_data

    # Generate multiple outputs
    summary = df.groupby(config.group_column).agg({
        config.value_column: ['mean', 'sum', 'count']
    }).round(2)

    details = df[df[config.value_column] > config.threshold]

    # Save outputs using datahub
    datahub.save("summary_stats", summary)
    datahub.save("filtered_details", details)

    logger.info(f"Saved summary ({len(summary)} groups) and details ({len(details)} rows)")
```

## Advanced Features

### 1. Context Access

Access the full execution context for advanced operations:

```python
@plugin(name="Context Aware Plugin", config=ContextConfig)
def context_aware_plugin(config: ContextConfig, logger, context) -> pd.DataFrame:
    """Plugin that uses execution context."""

    # Access project paths
    project_root = context.nexus_context.project_root
    case_path = context.nexus_context.case_path

    # Access configuration
    run_config = context.nexus_context.run_config

    # Access datahub
    datahub = context.datahub

    # Your logic here
    logger.info(f"Running in case: {case_path.name}")

    return config.input_data
```

### 2. Custom Data Handlers

Create custom data handlers for specialized formats:

```python
from pathlib import Path
from nexus.core.types import DataHandler

class CustomFormatHandler:
    """Handler for custom data format."""

    @property
    def produced_type(self) -> type:
        return pd.DataFrame

    def load(self, path: Path) -> pd.DataFrame:
        """Load custom format."""
        # Custom loading logic
        data = load_custom_format(path)
        return pd.DataFrame(data)

    def save(self, data: pd.DataFrame, path: Path) -> None:
        """Save in custom format."""
        # Custom saving logic
        save_custom_format(data, path)

# Register custom handler
from nexus.core.handlers import HANDLER_REGISTRY
HANDLER_REGISTRY["custom"] = CustomFormatHandler()
```

### 3. Plugin Dependencies

Plugins can depend on outputs from other plugins:

```python
class DependentConfig(PluginConfig):
    """Configuration for plugin with dependencies."""

    # Depends on output from previous plugin
    processed_data: Annotated[pd.DataFrame, DataSource(name="cleaned_data")]
    validation_report: Annotated[Dict, DataSource(name="validation_results")]

    additional_param: float = 1.0

@plugin(name="Dependent Plugin", config=DependentConfig)
def dependent_plugin(config: DependentConfig, logger) -> pd.DataFrame:
    """Plugin that depends on other plugin outputs."""

    # Check validation results
    if config.validation_report["status"] != "PASSED":
        logger.warning("Input data validation failed, proceeding with caution")

    # Process the already-cleaned data
    result = config.processed_data.copy()
    result["enhanced"] = result["value"] * config.additional_param

    return result
```

## Testing Plugins

### 1. Unit Tests

```python
import pytest
import pandas as pd
from nexus import create_engine

def test_my_plugin():
    """Test plugin functionality."""

    # Create test data
    test_data = pd.DataFrame({
        "id": [1, 2, 3],
        "value": [10, 20, 30],
        "category": ["A", "B", "A"]
    })

    # Create test configuration
    config = MyPluginConfig(
        input_data=test_data,
        threshold=15.0
    )

    # Execute plugin
    result = my_plugin(config, logger=None)

    # Assertions
    assert len(result) == 3
    assert "processed" in result.columns
    assert result["processed"].sum() == 2  # Values > 15
```

### 2. Integration Tests

```python
def test_plugin_in_pipeline(temp_project):
    """Test plugin within complete pipeline."""

    project_root, case_path = temp_project

    # Create engine
    engine = create_engine(project_root=project_root, case_path=case_path)

    # Run plugin
    result = engine.run_plugin("My Plugin", {"threshold": 0.8})

    # Verify results
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0
```

## Best Practices

### 1. Error Handling

```python
@plugin(name="Robust Plugin", config=RobustConfig)
def robust_plugin(config: RobustConfig, logger) -> pd.DataFrame:
    """Plugin with comprehensive error handling."""

    try:
        # Validate inputs
        if config.input_data.empty:
            raise ValueError("Input data is empty")

        if config.threshold < 0:
            raise ValueError("Threshold must be non-negative")

        # Process data
        result = process_data(config.input_data, config.threshold)

        # Validate outputs
        if result.empty:
            logger.warning("Processing resulted in empty dataset")

        return result

    except Exception as e:
        logger.error(f"Plugin execution failed: {e}")
        raise
```

### 2. Logging

```python
@plugin(name="Well Logged Plugin", config=LoggedConfig)
def well_logged_plugin(config: LoggedConfig, logger) -> pd.DataFrame:
    """Plugin with comprehensive logging."""

    logger.info(f"Starting processing with config: {config.dict()}")

    df = config.input_data
    logger.info(f"Input data shape: {df.shape}")
    logger.debug(f"Input columns: {list(df.columns)}")

    # Processing steps with logging
    logger.info("Applying filters...")
    filtered = df[df["value"] > config.threshold]
    logger.info(f"Filtered to {len(filtered)} rows")

    logger.info("Computing derived features...")
    filtered["derived"] = filtered["value"] * 2
    logger.debug(f"Added derived column with range: {filtered['derived'].min()}-{filtered['derived'].max()}")

    logger.info("Processing complete")
    return filtered
```

### 3. Performance

```python
@plugin(name="Optimized Plugin", config=OptimizedConfig)
def optimized_plugin(config: OptimizedConfig, logger) -> pd.DataFrame:
    """Performance-optimized plugin."""

    # Use vectorized operations
    df = config.input_data

    # Avoid loops, use pandas operations
    mask = df["value"] > config.threshold
    result = df[mask].copy()

    # Efficient memory usage
    if config.optimize_memory:
        result = optimize_dtypes(result)

    # Batch processing for large datasets
    if len(df) > config.batch_size:
        return process_in_batches(df, config)

    return result
```

### 4. Documentation

```python
@plugin(name="Well Documented Plugin", config=DocumentedConfig)
def documented_plugin(config: DocumentedConfig, logger) -> pd.DataFrame:
    """
    Process data with comprehensive documentation.

    This plugin performs advanced data processing including:
    - Data filtering based on configurable threshold
    - Feature engineering with derived columns
    - Quality validation and reporting

    Args:
        config: Plugin configuration containing:
            - input_data: Source DataFrame to process
            - threshold: Numeric threshold for filtering
            - create_features: Whether to create derived features
        logger: Logger instance for progress reporting

    Returns:
        pd.DataFrame: Processed data with new columns:
            - All original columns (filtered)
            - derived_feature: New computed column
            - quality_score: Data quality metric

    Raises:
        ValueError: If input data is empty or invalid
        ProcessingError: If processing fails due to data issues

    Example:
        >>> config = DocumentedConfig(
        ...     input_data=my_df,
        ...     threshold=0.5,
        ...     create_features=True
        ... )
        >>> result = documented_plugin(config, logger)
        >>> print(result.columns)
        ['original_col', 'derived_feature', 'quality_score']
    """

    # Implementation here
    pass
```

## Plugin Packaging

### 1. External Plugin Package

Create a separate package for distributable plugins:

```python
# my_custom_plugins/setup.py
from setuptools import setup, find_packages

setup(
    name="my-nexus-plugins",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "nexus>=0.2.0",
        "pandas>=1.5.0",
        # Additional dependencies
    ],
    entry_points={
        "nexus.plugins": [
            "my_plugin = my_custom_plugins.core:my_plugin",
        ]
    }
)
```

### 2. Plugin Discovery

Nexus automatically discovers plugins from:

1. Built-in plugins (`src/nexus/plugins/`)
2. Configured plugin paths (`config/global.yaml`)
3. Installed packages with entry points
4. Case-specific plugins (`cases/*/plugins/`)

## Troubleshooting

### Common Issues

1. **Plugin Not Found**
   - Check plugin registration with `nexus list`
   - Verify plugin decorator is correctly applied
   - Ensure plugin module is imported

2. **Configuration Errors**
   - Validate configuration class inherits from `PluginConfig`
   - Check type annotations are correct
   - Verify data source names match configuration

3. **Data Source Missing**
   - Check data source paths in configuration
   - Verify `must_exist` settings
   - Ensure data sources are properly registered

4. **Type Validation Errors**
   - Check Pydantic model validation
   - Verify type annotations match actual data
   - Review field constraints and validators

This guide provides a comprehensive foundation for developing robust, maintainable plugins for the Nexus framework. Follow these patterns and best practices to create plugins that integrate seamlessly with the framework's functional programming principles.