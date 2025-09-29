# Configuration Examples

This document provides comprehensive examples for configuring Nexus pipelines, plugins, and data sources.

## Table of Contents

1. [Basic Configuration](#basic-configuration)
2. [Global Configuration](#global-configuration)
3. [Case Configurations](#case-configurations)
4. [Pipeline Definitions](#pipeline-definitions)
5. [Data Source Configuration](#data-source-configuration)
6. [Plugin Configuration](#plugin-configuration)
7. [Advanced Scenarios](#advanced-scenarios)
8. [Environment-Specific Configuration](#environment-specific-configuration)

## Basic Configuration

### Minimal Setup

**config/global.yaml**
```yaml
framework:
  name: "nexus"

plugins:
  modules: []
  paths: []

plugin_defaults:
  "Data Generator":
    num_rows: 1000
    random_seed: 42
```

**cases/default/case.yaml**
```yaml
case_info:
  name: "Simple Pipeline"

pipeline:
  - plugin: "Data Generator"
```

## Global Configuration

### Complete Global Configuration

**config/global.yaml**
```yaml
# Framework configuration
framework:
  name: "nexus"
  version: "0.2.0"

  # Logging configuration
  logging:
    level: INFO
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

  # Plugin discovery settings
  plugin_discovery:
    auto_load_builtin: true
    search_paths:
      - "src/nexus/plugins"
      - "plugins"

  # Data processing defaults
  data:
    default_cache_size: 100  # MB
    lazy_loading: true

# Global plugin paths
plugins:
  modules:
    - "my_company.data_plugins"
    - "external_plugins"
  paths:
    - "custom_plugins/"
    - "/shared/plugins/"

# Default data source templates
data_source_templates:
  csv_template:
    handler: "csv"
    must_exist: true
    handler_args:
      encoding: "utf-8"
      sep: ","

  optional_csv:
    handler: "csv"
    must_exist: false

  parquet_template:
    handler: "parquet"
    must_exist: true
    handler_args:
      compression: "snappy"

# Global data sources (available to all cases)
data_sources:
  reference_data:
    handler: "csv"
    path: "shared/reference/master_data.csv"
    must_exist: true

  lookup_tables:
    handler: "json"
    path: "shared/config/lookup_tables.json"
    must_exist: true

# Global plugin defaults
plugin_defaults:
  "Data Generator":
    num_rows: 5000
    num_categories: 5
    noise_level: 0.1
    random_seed: 42

  "Data Cleaner":
    remove_outliers: true
    outlier_threshold: 2.5
    fill_missing: true
    missing_strategy: "median"

  "Data Validator":
    max_null_percentage: 0.05
    min_rows: 100

  "Data Quality Checker":
    check_duplicates: true
    check_data_types: true
    check_outliers: true
    outlier_threshold: 3.0

# Environment-specific overrides
environments:
  development:
    framework:
      logging:
        level: DEBUG
    plugins:
      "Data Generator":
        num_rows: 1000  # Smaller datasets for dev

  production:
    framework:
      logging:
        level: WARNING
      data:
        default_cache_size: 500  # More memory in production
    plugins:
      "Data Generator":
        num_rows: 100000  # Larger datasets for production
```

## Case Configurations

### Basic Data Processing Case

**cases/basic_processing/case.yaml**
```yaml
case_info:
  name: "Basic Data Processing"
  description: "Simple ETL pipeline for data cleaning and validation"
  version: "1.0.0"
  author: "Data Team"

pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 5000
      num_categories: 3
      noise_level: 0.2
    outputs:
      - name: "raw_data"

  - plugin: "Data Validator"
    config:
      required_columns: ["id", "category", "value", "score"]
      min_rows: 1000
      max_null_percentage: 0.1
    outputs:
      - name: "validation_report"

  - plugin: "Data Cleaner"
    config:
      remove_outliers: true
      outlier_threshold: 2.0
      fill_missing: true
      missing_strategy: "mean"
    outputs:
      - name: "clean_data"

data_sources:
  raw_data:
    handler: "csv"
    path: "data/generated_data.csv"
    must_exist: false

  clean_data:
    handler: "csv"
    path: "data/cleaned_data.csv"
    must_exist: false

  validation_report:
    handler: "json"
    path: "reports/validation.json"
    must_exist: false
```

### Advanced Analytics Case

**cases/advanced_analytics/case.yaml**
```yaml
case_info:
  name: "Advanced Analytics Pipeline"
  description: "Complex multi-stage analytics with feature engineering"
  version: "2.1.0"
  tags: ["analytics", "ml", "features"]

pipeline:
  # Data Generation
  - plugin: "Sample Data Generator"
    config:
      dataset_type: "sales"
      size: "large"
    outputs:
      - name: "raw_sales_data"

  # Data Validation
  - plugin: "Data Validator"
    config:
      required_columns:
        - "sale_id"
        - "product"
        - "quantity"
        - "unit_price"
        - "sale_date"
      min_rows: 5000
      max_null_percentage: 0.02
      numeric_range_checks:
        quantity:
          min: 1
          max: 1000
        unit_price:
          min: 0.01
          max: 10000
    outputs:
      - name: "sales_validation_report"

  # Data Cleaning
  - plugin: "Data Cleaner"
    config:
      remove_outliers: true
      outlier_threshold: 3.0
      fill_missing: true
      missing_strategy: "median"
    outputs:
      - name: "clean_sales_data"

  # Feature Engineering
  - plugin: "Data Transformer"
    config:
      normalize_columns: ["unit_price", "quantity"]
      log_transform_columns: ["unit_price"]
      create_derived_features: true
    outputs:
      - name: "featured_sales_data"

  # Aggregation
  - plugin: "Data Aggregator"
    config:
      group_by_column: "product"
      aggregation_method: "mean"
    outputs:
      - name: "product_aggregates"

  # Quality Assessment
  - plugin: "Data Quality Checker"
    config:
      check_duplicates: true
      check_data_types: true
      check_outliers: true
      outlier_threshold: 2.5
    outputs:
      - name: "final_quality_report"

# Case-specific data sources
data_sources:
  raw_sales_data:
    handler: "csv"
    path: "data/raw_sales.csv"
    must_exist: false
    handler_args:
      encoding: "utf-8"

  clean_sales_data:
    handler: "parquet"
    path: "data/clean_sales.parquet"
    must_exist: false
    handler_args:
      compression: "snappy"

  featured_sales_data:
    handler: "parquet"
    path: "data/featured_sales.parquet"
    must_exist: false

  product_aggregates:
    handler: "csv"
    path: "data/product_summary.csv"
    must_exist: false

  sales_validation_report:
    handler: "json"
    path: "reports/sales_validation.json"
    must_exist: false

  final_quality_report:
    handler: "json"
    path: "reports/quality_assessment.json"
    must_exist: false

# Case-specific plugin overrides
plugins:
  "Sample Data Generator":
    # Override global defaults for this case
    random_seed: 999

  "Data Cleaner":
    # More aggressive cleaning for this case
    outlier_threshold: 2.0
    missing_strategy: "drop"  # Override global median strategy
```

## Pipeline Definitions

### Sequential Processing Pipeline

```yaml
pipeline:
  # Stage 1: Data Ingestion
  - plugin: "Data Generator"
    config:
      num_rows: 10000
      num_categories: 5
    outputs:
      - name: "source_data"

  # Stage 2: Initial Validation
  - plugin: "Data Validator"
    config:
      required_columns: ["id", "category", "value"]
      min_rows: 5000
    outputs:
      - name: "ingestion_validation"

  # Stage 3: Data Cleaning
  - plugin: "Data Cleaner"
    config:
      remove_outliers: true
      fill_missing: true
    outputs:
      - name: "cleaned_data"

  # Stage 4: Feature Engineering
  - plugin: "Data Transformer"
    config:
      normalize_columns: ["value"]
      create_derived_features: true
    outputs:
      - name: "engineered_data"

  # Stage 5: Final Quality Check
  - plugin: "Data Quality Checker"
    config:
      check_duplicates: true
      check_outliers: true
    outputs:
      - name: "quality_report"
```

### Parallel Processing Pipeline

```yaml
pipeline:
  # Data Generation
  - plugin: "Data Generator"
    config:
      num_rows: 50000
    outputs:
      - name: "base_data"

  # Parallel Branch 1: Statistical Analysis
  - plugin: "Statistical Analyzer"
    config:
      include_correlations: true
      include_distributions: true
    outputs:
      - name: "statistics_report"

  # Parallel Branch 2: Data Quality Assessment
  - plugin: "Data Quality Checker"
    config:
      comprehensive_check: true
    outputs:
      - name: "quality_metrics"

  # Parallel Branch 3: Feature Engineering
  - plugin: "Data Transformer"
    config:
      create_all_features: true
    outputs:
      - name: "feature_data"
```

## Data Source Configuration

### File-Based Data Sources

```yaml
data_sources:
  # CSV with custom settings
  sales_data:
    handler: "csv"
    path: "data/sales_2024.csv"
    must_exist: true
    handler_args:
      sep: ";"
      encoding: "latin-1"
      index_col: 0
      parse_dates: ["sale_date"]

  # Parquet with compression
  large_dataset:
    handler: "parquet"
    path: "data/large_dataset.parquet"
    must_exist: true
    handler_args:
      compression: "gzip"
      engine: "pyarrow"

  # JSON configuration
  metadata:
    handler: "json"
    path: "config/metadata.json"
    must_exist: true
    handler_args:
      indent: 2

  # Optional data source
  supplementary_data:
    handler: "csv"
    path: "data/supplementary.csv"
    must_exist: false  # Won't fail if missing
```

### Dynamic Path Configuration

```yaml
data_sources:
  # Date-based paths
  daily_data:
    handler: "csv"
    path: "data/daily/{{ date }}/transactions.csv"
    must_exist: true

  # Environment-based paths
  config_file:
    handler: "json"
    path: "config/{{ environment }}/settings.json"
    must_exist: true

  # Parameterized outputs
  processed_output:
    handler: "parquet"
    path: "output/{{ case_name }}/{{ timestamp }}/result.parquet"
    must_exist: false
```

## Plugin Configuration

### Data Generator Examples

```yaml
plugins:
  "Data Generator":
    # Basic configuration
    num_rows: 10000
    num_categories: 3
    random_seed: 42

    # Advanced configuration
    noise_level: 0.15
    distribution_type: "normal"
    category_weights: [0.5, 0.3, 0.2]

    # Output customization
    include_timestamps: true
    timestamp_start: "2024-01-01"
    timestamp_freq: "1H"

  "Sample Data Generator":
    dataset_type: "customers"
    size: "medium"
    include_demographics: true
    anonymize_pii: true
```

### Data Processing Examples

```yaml
plugins:
  "Data Cleaner":
    # Outlier handling
    remove_outliers: true
    outlier_method: "iqr"  # or "zscore", "isolation_forest"
    outlier_threshold: 2.5

    # Missing value handling
    fill_missing: true
    missing_strategy: "median"  # or "mean", "mode", "drop", "interpolate"
    missing_threshold: 0.5  # Drop columns with >50% missing

    # Data type optimization
    optimize_dtypes: true
    categorical_threshold: 0.1  # Convert to category if <10% unique

  "Data Transformer":
    # Normalization
    normalize_columns: ["price", "quantity", "value"]
    normalization_method: "minmax"  # or "zscore", "robust"

    # Transformations
    log_transform_columns: ["price", "income"]
    sqrt_transform_columns: ["area"]

    # Feature engineering
    create_derived_features: true
    interaction_features: true
    polynomial_features: false
    polynomial_degree: 2

    # Binning
    bin_columns:
      age: [0, 18, 35, 50, 65, 100]
      income: [0, 30000, 60000, 100000, 200000]
```

### Validation Examples

```yaml
plugins:
  "Data Validator":
    # Basic validation
    required_columns: ["id", "timestamp", "value"]
    min_rows: 1000
    max_rows: 1000000

    # Null value constraints
    max_null_percentage: 0.05
    null_tolerant_columns: ["optional_field", "comments"]

    # Data type validation
    expected_dtypes:
      id: "int64"
      timestamp: "datetime64[ns]"
      category: "object"
      value: "float64"

    # Value range validation
    numeric_range_checks:
      value:
        min: 0
        max: 1000
      percentage:
        min: 0.0
        max: 1.0

    # Pattern validation
    pattern_checks:
      email: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
      phone: "^\\+?1?[0-9]{10,14}$"

    # Custom validation rules
    custom_rules:
      - name: "future_dates"
        expression: "timestamp > datetime.now()"
        allow_violations: 0

  "Data Quality Checker":
    # Comprehensive checking
    check_duplicates: true
    check_data_types: true
    check_outliers: true
    check_consistency: true

    # Outlier detection
    outlier_threshold: 3.0
    outlier_methods: ["zscore", "iqr"]

    # Duplicate detection
    duplicate_subset: ["id", "timestamp"]  # Check duplicates on specific columns

    # Consistency checks
    consistency_rules:
      - columns: ["start_date", "end_date"]
        rule: "start_date < end_date"
      - columns: ["quantity", "unit_price", "total"]
        rule: "abs(quantity * unit_price - total) < 0.01"
```

## Advanced Scenarios

### Multi-Source Data Integration

```yaml
case_info:
  name: "Multi-Source Integration"
  description: "Integrate data from multiple sources"

pipeline:
  # Load and validate multiple sources
  - plugin: "Multi Source Loader"
    config:
      sources:
        - name: "transactions"
          path: "data/transactions.csv"
          required: true
        - name: "customers"
          path: "data/customers.csv"
          required: true
        - name: "products"
          path: "data/products.csv"
          required: false
    outputs:
      - name: "raw_sources"

  # Join data sources
  - plugin: "Data Joiner"
    config:
      joins:
        - left: "transactions"
          right: "customers"
          on: "customer_id"
          how: "left"
        - left: "result"
          right: "products"
          on: "product_id"
          how: "left"
    outputs:
      - name: "integrated_data"

data_sources:
  transactions:
    handler: "csv"
    path: "sources/transactions.csv"
    handler_args:
      parse_dates: ["transaction_date"]

  customers:
    handler: "csv"
    path: "sources/customers.csv"

  products:
    handler: "csv"
    path: "sources/products.csv"
    must_exist: false
```

### Conditional Processing

```yaml
pipeline:
  - plugin: "Data Generator"
    outputs:
      - name: "raw_data"

  - plugin: "Data Quality Checker"
    outputs:
      - name: "quality_assessment"

  # Conditional processing based on quality
  - plugin: "Conditional Processor"
    config:
      condition: "quality_assessment.overall_score > 0.8"
      true_pipeline:
        - plugin: "Standard Cleaner"
      false_pipeline:
        - plugin: "Aggressive Cleaner"
        - plugin: "Additional Validation"
    outputs:
      - name: "processed_data"
```

### Iterative Processing

```yaml
pipeline:
  - plugin: "Data Generator"
    outputs:
      - name: "initial_data"

  # Iterative refinement
  - plugin: "Iterative Processor"
    config:
      max_iterations: 5
      convergence_threshold: 0.01
      iteration_steps:
        - plugin: "Data Cleaner"
        - plugin: "Quality Checker"
        - plugin: "Convergence Checker"
    outputs:
      - name: "refined_data"
      - name: "iteration_log"
```

## Environment-Specific Configuration

### Development Environment

**config/environments/development.yaml**
```yaml
framework:
  logging:
    level: DEBUG

data_sources:
  # Use sample data in development
  production_data:
    handler: "csv"
    path: "sample_data/dev_sample.csv"

plugins:
  "Data Generator":
    num_rows: 1000  # Smaller datasets

  "Data Quality Checker":
    quick_check: true  # Faster checks in dev
```

### Production Environment

**config/environments/production.yaml**
```yaml
framework:
  logging:
    level: WARNING

  data:
    default_cache_size: 1000  # More memory

data_sources:
  # Production data sources
  production_data:
    handler: "parquet"
    path: "/data/warehouse/production_dataset.parquet"
    handler_args:
      compression: "snappy"

plugins:
  "Data Generator":
    num_rows: 1000000  # Full datasets

  "Data Quality Checker":
    comprehensive_check: true
    generate_detailed_report: true
```

### Testing Environment

**config/environments/testing.yaml**
```yaml
framework:
  logging:
    level: INFO

plugins:
  "Data Generator":
    num_rows: 100  # Minimal data for tests
    random_seed: 12345  # Fixed seed for reproducibility

  "Data Validator":
    fail_on_warnings: true  # Strict validation in tests
```

These configuration examples demonstrate the flexibility and power of the Nexus configuration system. You can mix and match these patterns to create configurations that perfectly fit your data processing needs.