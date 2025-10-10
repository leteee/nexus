# Plugins API Reference

This directory contains auto-generated documentation for all available plugins.

**Total Plugins**: 5

## Available Plugins

### [Data Aggregator](data_aggregator.md)

    Aggregate data by grouping columns.

    Groups data by specified column(s) and applies aggregation functions.
    Common for generating summary statistics and rollups.

    Supported aggregation functions:
    - 'mean' : Average value
    - 'sum' : Total sum
    - 'count' : Count of records
    - 'min' : Minimum value
    - 'max' : Maximum value
    - 'std' : Standard deviation

    Returns:
        Aggregated DataFrame with group statistics
    

### [Data Filter](data_filter.md)

    Filter data based on column conditions.

    Applies filtering conditions to a dataset and optionally removes null values.
    Useful for data cleaning and subsetting operations.

    Supported operators:
    - '>' : Greater than
    - '<' : Less than
    - '>=' : Greater than or equal
    - '<=' : Less than or equal
    - '==' : Equal to
    - '!=' : Not equal to

    Returns:
        Filtered DataFrame with matching rows
    

### [Data Generator](data_generator.md)

    Generate synthetic dataset with configurable characteristics.

    Creates realistic test data with various data types,
    controllable noise levels, and optional outliers.
    

### [Data Validator](data_validator.md)

    Validate data quality and generate report.

    Performs comprehensive data quality checks including:
    - Null value detection
    - Duplicate record detection
    - Data type validation
    - Required column verification

    Returns:
        Validation report dictionary with check results
    

### [Sample Data Generator](sample_data_generator.md)

    Generate predefined sample datasets for testing and demos.
    
