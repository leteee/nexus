# Nexus Framework - Configuration Best Practices

This guide provides comprehensive best practices for configuring the Nexus framework, covering plugin configuration, data source management, path setup, and advanced configuration patterns.

## Table of Contents

1. [Configuration Hierarchy](#configuration-hierarchy)
2. [Plugin Configuration](#plugin-configuration)
3. [Data Source Configuration](#data-source-configuration)
4. [Path Configuration](#path-configuration)
5. [Template and Case Organization](#template-and-case-organization)
6. [Environment Management](#environment-management)
7. [Performance Configuration](#performance-configuration)
8. [Security Best Practices](#security-best-practices)
9. [Troubleshooting](#troubleshooting)

## Configuration Hierarchy

Nexus uses a hierarchical configuration system where settings can be overridden at multiple levels. Understanding this hierarchy is crucial for effective configuration management.

### Priority Order (highest to lowest)

1. **CLI overrides** (`--config key=value`)
2. **Case-specific configurations** (`cases/*/case.yaml`)
3. **Template configurations** (`templates/*.yaml`) **[RECOMMENDED]**
4. **Global defaults** (`config/global.yaml`)
5. **Plugin built-in defaults**

### Best Practice: Use Templates for Reusable Patterns

```yaml
# templates/analytics.yaml - RECOMMENDED approach
pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 5000        # Template-specific default
      random_seed: 42
    outputs:
      - name: "raw_data"

  - plugin: "Data Cleaner"
    config:
      outlier_threshold: 2.0
      missing_strategy: "median"
    outputs:
      - name: "clean_data"
```

## Plugin Configuration

### 1. Configuration Location Guidelines

| Location | Use Case | Example |
|----------|----------|---------|
| **Templates** | Reusable pipeline patterns | `templates/etl-pipeline.yaml` |
| **Case configs** | Case-specific customizations | `cases/finance/case.yaml` |
| **CLI overrides** | Quick experimentation | `--config plugins.DataGenerator.num_rows=1000` |
| **Global config** | Organization-wide defaults | `config/global.yaml` (sparingly) |

### 2. Plugin Parameter Patterns

#### Good: Clear, Descriptive Configuration
```yaml
# templates/data-quality.yaml
pipeline:
  - plugin: "Data Validator"
    config:
      required_columns: ["customer_id", "email", "purchase_date"]
      max_null_percentage: 0.02  # 2% maximum
      numeric_range_checks:
        age:
          min: 18
          max: 100
        purchase_amount:
          min: 0
          max: 10000
    outputs:
      - name: "validation_report"
```

#### Avoid: Global Configuration for Specific Use Cases
```yaml
# config/global.yaml - AVOID this pattern
plugin_defaults:
  "Data Validator":
    required_columns: ["customer_id"]  # Too specific for global config
```

### 3. Dynamic Configuration with CLI Overrides

```bash
# Good: Quick experimentation
nexus run --template analytics --config plugins.DataGenerator.num_rows=10000

# Good: Multiple overrides
nexus run --template etl-pipeline \
  --config plugins.DataCleaner.outlier_threshold=3.0 \
  --config plugins.DataTransformer.normalize_columns='["age","income"]'
```

### 4. Plugin Configuration Documentation

Use the built-in help system to understand plugin parameters:

```bash
# Show detailed plugin documentation
nexus help --plugin "Data Generator"

# Show all available plugins
nexus help --all
```

## Data Source Configuration

### 1. Data Source Naming Conventions

Use descriptive names that match your plugin's DataSource annotations:

```python
# Plugin definition
class MyPluginConfig(PluginConfig):
    input_data: Annotated[pd.DataFrame, DataSource(name="customer_transactions")]
    output_file: Annotated[str, DataSink(name="processed_customers")]
```

```yaml
# Corresponding data source configuration
data_sources:
  customer_transactions:
    handler: "parquet"
    path: "data/raw_transactions.parquet"
    must_exist: true

  processed_customers:
    handler: "csv"
    path: "reports/processed_customers.csv"
    must_exist: false
```

### 2. Handler Selection Guidelines

| File Type | Recommended Handler | Use Case |
|-----------|-------------------|----------|
| **CSV** | `csv` | Small to medium datasets, human-readable |
| **Parquet** | `parquet` | Large datasets, efficient storage |
| **JSON** | `json` | Configuration, metadata, small structured data |
| **Pickle** | `pickle` | Python objects, temporary storage |

### 3. Data Source Templates

Use data source templates for consistency:

```yaml
# config/global.yaml
data_source_templates:
  large_dataset:
    handler: "parquet"
    must_exist: true
    path: "data/{name}.parquet"

  report_output:
    handler: "json"
    must_exist: false
    path: "reports/{name}.json"
```

```yaml
# templates/analytics.yaml - Using templates
data_sources:
  sales_data:
    <<: *large_dataset  # YAML anchor reference
    path: "data/sales_transactions.parquet"

  analytics_report:
    <<: *report_output
    path: "reports/sales_analytics.json"
```

### 4. Automatic Data Source Discovery

**New Feature**: Nexus automatically discovers data files in case directories, making single plugin execution more convenient.

#### How Auto-Discovery Works

For single plugin execution (`nexus plugin`), the engine automatically scans:
- Case root directory
- `data/` subdirectory (if exists)

#### Supported File Formats

| Extension | Handler | Description |
|-----------|---------|-------------|
| `.csv` | `csv` | Comma-separated values |
| `.json` | `json` | JSON data files |
| `.parquet` | `parquet` | Columnar storage format |
| `.xlsx` | `excel` | Excel spreadsheets |
| `.xml` | `xml` | XML documents |

#### Auto-Discovery Examples

```bash
# Case directory structure
cases/analysis/
├── case.yaml          # Optional - if missing, auto-discovery kicks in
├── customer_data.csv   # Auto-discovered as "customer_data"
├── config.json        # Auto-discovered as "config"
└── data/
    ├── sales.parquet   # Auto-discovered as "sales"
    └── returns.csv     # Auto-discovered as "returns"

# Single plugin execution with auto-discovery
nexus plugin "Data Validator" --case analysis
# Plugin can access: customer_data, config, sales, returns
```

#### Best Practices for Auto-Discovery

✅ **Good**:
```yaml
# Use descriptive filenames that match plugin expectations
data/
├── customer_transactions.csv
├── product_catalog.json
└── sales_summary.parquet
```

✅ **Good**: Combine with explicit configuration when needed
```yaml
# case.yaml - Mix explicit and auto-discovered sources
data_sources:
  # Explicit configuration for critical sources
  main_dataset:
    handler: "parquet"
    path: "data/transactions.parquet"
    must_exist: true
    # Auto-discovered sources will be added automatically
```

❌ **Avoid**:
```yaml
# Generic filenames that don't indicate content
data/
├── data.csv       # Too generic
├── file1.json     # Not descriptive
└── temp.xlsx      # Unclear purpose
```

#### When Auto-Discovery is Used

1. **Single Plugin Execution**: When running `nexus plugin` and no `case.yaml` exists
2. **Case Execution**: Auto-discovered sources supplement explicitly defined ones
3. **Development**: Quick testing with new data files without configuration updates

#### Auto-Discovery Configuration

Control auto-discovery behavior in global config:

```yaml
# config/global.yaml
framework:
  auto_discovery:
    enabled: true
    scan_subdirectories: ["data", "input", "source"]
    file_extensions: [".csv", ".json", ".parquet", ".xlsx", ".xml"]
    naming_conflicts: "suffix"  # suffix, prefix, error
```

## Path Configuration

### 1. Plugin and Handler Discovery

Configure plugin and handler paths with flexibility in mind:

```yaml
# config/global.yaml
plugins:
  # Module paths (Python imports)
  modules:
    - "company.nexus_plugins"     # Company-specific plugins
    - "department.custom_plugins"  # Department-specific plugins

  # Directory paths (support multiple formats)
  paths:
    - "plugins"                   # Relative to project root
    - "${NEXUS_PLUGINS_DIR}"     # Environment variable
    - "~/shared_plugins"          # Home directory
    - "/opt/nexus/plugins"        # Absolute path

handlers:
  paths:
    - "custom_handlers"           # Relative path
    - "${CUSTOM_HANDLERS_PATH}"   # Environment variable
```

### 2. Case-Specific Plugin Discovery

```bash
# Directory structure
cases/
├── financial-analysis/
│   ├── plugins/           # Case-specific plugins
│   │   └── finance_plugin.py
│   ├── handlers/          # Case-specific handlers
│   │   └── excel_handler.py
│   └── analytics.yaml
```

### 3. Path Resolution Examples

```yaml
# All these path formats are supported:
plugins:
  paths:
    - "plugins"                    # → project_root/plugins/
    - "./custom_plugins"           # → project_root/custom_plugins/
    - "../shared/nexus_plugins"    # → project_root/../shared/nexus_plugins/
    - "~/company_plugins"          # → /home/user/company_plugins/
    - "/opt/global/plugins"        # → /opt/global/plugins/
    - "${PLUGINS_DIR}/nexus"       # → $PLUGINS_DIR/nexus/
```

## Template and Case Organization

### 1. Template Organization

```
templates/
├── default.yaml              # Basic processing
├── etl-pipeline.yaml         # Extract, Transform, Load
├── analytics.yaml            # Data analysis
├── data-quality.yaml         # Quality assessment
├── ml-preprocessing.yaml     # Machine learning prep
└── compliance/               # Domain-specific templates
    ├── gdpr-analysis.yaml
    └── financial-audit.yaml
```

### 2. Case Organization

```
cases/
├── default/                  # Default case space
├── financial-analysis/       # Financial data analysis
│   ├── data/                # Input data files
│   ├── reports/             # Generated reports
│   ├── config/              # Case-specific config
│   ├── analytics.yaml       # Customized template
│   └── case.yaml           # Case configuration
├── customer-segmentation/    # Customer analysis
└── compliance-audit/        # Compliance checking
```

### 3. Case Configuration Best Practices

```yaml
# cases/financial-analysis/case.yaml
case_info:
  name: "Q4 Financial Analysis"
  description: "Quarterly financial data analysis and reporting"
  owner: "finance-team"
  created: "2024-01-15"

# Case-specific plugin overrides
plugins:
  "Data Generator":
    # Override for this specific case
    dataset_type: "financial_transactions"
    size: "large"

# Case-specific data sources
data_sources:
  quarterly_transactions:
    handler: "parquet"
    path: "data/q4_transactions.parquet"
    must_exist: true
```

## Environment Management

### 1. Environment-Specific Configuration

```yaml
# config/global.yaml
environments:
  development:
    framework:
      logging:
        level: DEBUG
    plugin_defaults:
      "Data Generator":
        num_rows: 100        # Small datasets for dev

  staging:
    framework:
      logging:
        level: INFO
    plugin_defaults:
      "Data Generator":
        num_rows: 5000       # Medium datasets for staging

  production:
    framework:
      logging:
        level: WARNING
      performance:
        max_concurrent_plugins: 8
    plugin_defaults:
      "Data Generator":
        num_rows: 50000      # Large datasets for production
```

### 2. Environment Selection

```bash
# Set environment via environment variable
export NEXUS_ENV=production
nexus run --template analytics

# Or via configuration override
nexus run --template analytics --config framework.environment=staging
```

## Performance Configuration

### 1. Memory and Caching

```yaml
# config/global.yaml
framework:
  performance:
    default_cache_size: 500      # MB
    lazy_loading: true           # Load data on demand
    max_concurrent_plugins: 4    # Limit parallel execution
    gc_threshold: 1000          # Garbage collection threshold
```

### 2. Plugin-Specific Performance

```yaml
# templates/high-performance.yaml
plugins:
  "Data Transformer":
    batch_size: 10000           # Process in batches
    use_multiprocessing: true   # Enable multiprocessing
    n_jobs: -1                 # Use all available cores
```

### 3. Data Source Optimization

```yaml
data_sources:
  large_dataset:
    handler: "parquet"          # Efficient columnar format
    path: "data/large_data.parquet"
    compression: "snappy"       # Fast compression
    chunk_size: 10000          # Read in chunks
```

## Security Best Practices

### 1. Credential Management

```yaml
# Good: Use environment variables
data_sources:
  database_connection:
    handler: "sql"
    connection_string: "${DATABASE_URL}"  # Environment variable
    username: "${DB_USERNAME}"
    password: "${DB_PASSWORD}"

# Bad: Hardcoded credentials
data_sources:
  database_connection:
    username: "admin"              # NEVER do this
    password: "password123"        # NEVER do this
```

### 2. Path Security

```yaml
# Good: Restrict paths to project directory
plugins:
  paths:
    - "plugins"                   # Safe: relative to project
    - "./custom_plugins"          # Safe: explicit relative

# Caution: Absolute paths
plugins:
  paths:
    - "/opt/nexus/plugins"        # OK if controlled environment
    - "~/plugins"                 # Use with caution
```

### 3. Plugin Security

```python
# Plugin security checklist:
# ✓ Validate all inputs
# ✓ Use type hints and Pydantic validation
# ✓ Avoid shell command execution
# ✓ Sanitize file paths
# ✓ Use secure temporary files

@plugin(name="Secure Plugin", config=SecureConfig)
def secure_plugin(config: SecureConfig, logger) -> pd.DataFrame:
    # Validate inputs
    if not config.input_path.is_file():
        raise ValueError("Input path is not a valid file")

    # Use secure operations
    return pd.read_csv(config.input_path)
```

## Troubleshooting

### 1. Configuration Debugging

```bash
# Debug configuration issues
nexus --log-level DEBUG run --template analytics

# Check plugin discovery
nexus list

# Show plugin documentation
nexus help --plugin "Data Generator"

# Show all available help
nexus help --all
```

### 2. Common Configuration Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Plugin not found | Plugin not in discovery paths | Check `plugins.paths` configuration |
| Data source not found | Wrong data source name | Match plugin DataSource annotation |
| Template not found | Template not in templates/ | Create template or check template name |
| Permission denied | Incorrect file permissions | Check file/directory permissions |
| Path not found | Relative path resolution | Use absolute paths or check project root |

### 3. Validation Commands

```bash
# Validate configuration
nexus run --template analytics --dry-run  # If implemented

# Test plugin execution
nexus plugin "Data Generator" --config num_rows=10

# List available templates
nexus template list

# Check discovery paths
nexus help --all | grep "Discovered"
```

### 4. Configuration Schema Validation

Use the help system to understand expected configuration format:

```bash
# Show plugin parameters and types
nexus help --plugin "Data Validator"

# Show handler documentation
nexus help --handler csv
```

## Advanced Patterns

### 1. Configuration Inheritance

```yaml
# templates/base-etl.yaml
base_etl: &base_etl
  pipeline:
    - plugin: "Data Validator"
      config:
        max_null_percentage: 0.05
    - plugin: "Data Cleaner"
      config:
        remove_outliers: true

# templates/financial-etl.yaml
<<: *base_etl
case_info:
  name: "Financial ETL Pipeline"
plugins:
  "Data Validator":
    required_columns: ["transaction_id", "amount", "date"]
```

### 2. Dynamic Configuration

```python
# Dynamic configuration in Python
import nexus
from pathlib import Path

# Build configuration dynamically
config = {
    "plugins": {
        "Data Generator": {
            "num_rows": 1000 if is_development else 10000,
            "random_seed": 42
        }
    }
}

# Run with dynamic configuration
nexus.run_pipeline(
    template_name="analytics",
    config_overrides=config
)
```

### 3. Configuration Validation

```python
# Custom configuration validation
from pydantic import BaseModel, validator

class CustomPluginConfig(PluginConfig):
    threshold: float

    @validator('threshold')
    def validate_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('threshold must be between 0 and 1')
        return v
```

This comprehensive guide should help you configure Nexus effectively for any use case, from simple data processing to complex enterprise deployments.
