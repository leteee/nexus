# Nexus Example Cases

This directory contains curated examples demonstrating Nexus framework capabilities.

## Available Cases

### 1. `quickstart` - Quick Start ⚡
**Purpose**: Minimal working example
**Features**:
- Single plugin execution
- Direct path configuration
- Automatic DataSink handling

**Run**:
```bash
nexus run --case quickstart
```

**Output**:
- `data/synthetic_data.csv` - 1000 rows of generated data

---

### 2. `hybrid-paths` - Hybrid Path Resolution 🔀
**Purpose**: Demonstrate all three path resolution strategies
**Features**:
- ✅ Explicit logical names (`@customer_master`)
- ✅ Implicit logical names (`product_catalog`)
- ✅ Direct paths (`temp/file.csv`)
- ✅ Global `data_sources` registry

**Run**:
```bash
nexus run --case hybrid-paths
```

**Output**:
- `temp/customers_generated.csv`
- `temp/sales_generated.csv`

**Path Resolution Strategies**:
```yaml
# In config:
input1: "@customer_master"    # Explicit (@ prefix) - recommended
input2: "product_catalog"     # Implicit (auto-detected)
input3: "temp/data.csv"       # Direct path
input4: "@2024-sales"         # Special names (@ required)
```

---

### 3. `pipeline-flow` - Pipeline Data Flow 🔄
**Purpose**: Multi-step data transformation pipeline
**Features**:
- Multiple pipeline steps
- Data flowing between steps
- Configuration overrides
- Reproducible results (fixed seed)

**Run**:
```bash
nexus run --case pipeline-flow
```

**Output**:
- `data/01_raw_data.csv` - 5000 rows synthetic data
- `data/02_products.csv` - 10000 product records

---

### 4. `multi-output` - Multi-Output Plugins 📦
**Purpose**: Template for plugins with multiple outputs
**Features**:
- Plugin returns dictionary
- Multiple output paths
- Train/test/validation split example

**Status**: Template (requires multi-output plugin implementation)

---

## Quick Reference

### Run a Case
```bash
# Using short name
nexus run --case quickstart

# Using full path
nexus run --case /path/to/case/case.yaml
```

### List Available Cases
```bash
nexus list
```

### Plugin Documentation
```bash
nexus plugin describe "Data Generator"
```

---

## Case Structure

Each case directory contains:
```
case-name/
├── case.yaml          # Pipeline configuration
├── data/              # Output data files (created on run)
└── reports/           # Output reports (if applicable)
```

---

## Creating Your Own Case

1. **Create directory**: `cases/my-case/`
2. **Create `case.yaml`**:
```yaml
case_info:
  name: "My Custom Case"
  description: "What this case demonstrates"

pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 1000
      output_data: "data/my_output.csv"
```
3. **Run**: `nexus run --case my-case`

---

## Core Concepts Demonstrated

### DataSource/DataSink in Config
All I/O configuration is in the plugin config:
```yaml
config:
  input_data: "path/to/input.csv"    # DataSource
  output_data: "path/to/output.csv"  # DataSink
  some_param: true                   # Behavior config
```

### Global Data Sources (Optional)
Define reusable data sources:
```yaml
data_sources:
  master_data:
    handler: "parquet"
    path: "/warehouse/data.parquet"

pipeline:
  - plugin: "My Plugin"
    config:
      input: "@master_data"  # Reference global source
```

### Path Resolution Priority
1. **Explicit** (`@name`) → Must exist in `data_sources`
2. **Implicit** (`name`) → If exists in `data_sources` and valid identifier
3. **Direct** (`path/file`) → Literal path

---

## Next Steps

- Explore each case to understand framework capabilities
- Modify cases to experiment with configurations
- Create your own cases for specific workflows
- Check `docs/` for detailed documentation
