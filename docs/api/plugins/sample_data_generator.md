# Sample Data Generator

## Overview

Generate predefined sample datasets for testing and demos.

## Configuration

```yaml
pipeline:
  - plugin: "Sample Data Generator"
    config:
      output_data: "data/sample_data.csv"  # str
      dataset_type: "sales"  # str
      size: "small"  # str
```

## CLI Usage

```bash
# Run with defaults
nexus plugin "Sample Data Generator" --case mycase

# Run with custom config
nexus plugin "Sample Data Generator" --case mycase \
  -C output_data=value \
  -C dataset_type=value
```
