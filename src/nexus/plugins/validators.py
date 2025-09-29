"""
Built-in data validation plugins.

These plugins provide data quality checks and validation
following data_replay's validation patterns.
"""

from typing import Annotated, Dict, Any
import pandas as pd
import numpy as np

from nexus import plugin, PluginConfig, DataSource, DataSink


class DataValidatorConfig(PluginConfig):
    """Configuration for data validation."""

    input_data: Annotated[pd.DataFrame, DataSource(name="generated_data")]
    required_columns: list[str] = []
    min_rows: int = 1
    max_null_percentage: float = 0.1
    numeric_range_checks: Dict[str, Dict[str, float]] = {}
    output_report: Annotated[str, DataSink(name="validation_report")] = "validation_report.json"


class DataQualityConfig(PluginConfig):
    """Configuration for comprehensive data quality assessment."""

    input_data: Annotated[pd.DataFrame, DataSource(name="transformed_data")]
    check_duplicates: bool = True
    check_data_types: bool = True
    check_outliers: bool = True
    outlier_threshold: float = 3.0
    output_report: Annotated[str, DataSink(name="quality_report")] = "quality_report.json"


@plugin(name="Data Validator", config=DataValidatorConfig)
def validate_data(config: DataValidatorConfig, logger) -> Dict[str, Any]:
    """
    Validate dataset against specified quality criteria.

    Returns a comprehensive validation report with pass/fail status
    and detailed metrics for each validation check.
    """
    df = config.input_data
    logger.info(f"Validating dataset: {df.shape}")

    validation_report = {
        'status': 'PASSED',
        'issues': [],
        'metrics': {
            'row_count': len(df),
            'column_count': len(df.columns),
            'null_percentage': (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100,
            'duplicate_rows': df.duplicated().sum(),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
        },
        'column_details': {}
    }

    # Check minimum row count
    if len(df) < config.min_rows:
        validation_report['status'] = 'FAILED'
        validation_report['issues'].append(
            f"Insufficient rows: {len(df)} < {config.min_rows}"
        )

    # Check required columns
    missing_cols = set(config.required_columns) - set(df.columns)
    if missing_cols:
        validation_report['status'] = 'FAILED'
        validation_report['issues'].append(
            f"Missing required columns: {list(missing_cols)}"
        )

    # Check null percentage
    null_pct = validation_report['metrics']['null_percentage']
    if null_pct > config.max_null_percentage * 100:
        validation_report['status'] = 'FAILED'
        validation_report['issues'].append(
            f"Too many nulls: {null_pct:.1f}% > {config.max_null_percentage * 100}%"
        )

    # Check numeric ranges
    for col_name, range_check in config.numeric_range_checks.items():
        if col_name in df.columns and df[col_name].dtype in [np.number]:
            col_data = df[col_name].dropna()

            if 'min' in range_check:
                min_violations = (col_data < range_check['min']).sum()
                if min_violations > 0:
                    validation_report['issues'].append(
                        f"Column '{col_name}': {min_violations} values below minimum {range_check['min']}"
                    )

            if 'max' in range_check:
                max_violations = (col_data > range_check['max']).sum()
                if max_violations > 0:
                    validation_report['issues'].append(
                        f"Column '{col_name}': {max_violations} values above maximum {range_check['max']}"
                    )

    # Generate column-level details
    for col in df.columns:
        col_info = {
            'dtype': str(df[col].dtype),
            'null_count': int(df[col].isnull().sum()),
            'unique_count': int(df[col].nunique()),
        }

        if df[col].dtype in [np.number]:
            col_info.update({
                'mean': float(df[col].mean()) if not df[col].isnull().all() else None,
                'std': float(df[col].std()) if not df[col].isnull().all() else None,
                'min': float(df[col].min()) if not df[col].isnull().all() else None,
                'max': float(df[col].max()) if not df[col].isnull().all() else None,
            })

        validation_report['column_details'][col] = col_info

    status = validation_report['status']
    issue_count = len(validation_report['issues'])
    logger.info(f"Validation {status}: {issue_count} issues found")

    return validation_report


@plugin(name="Data Quality Checker", config=DataQualityConfig)
def assess_data_quality(config: DataQualityConfig, logger) -> Dict[str, Any]:
    """
    Perform comprehensive data quality assessment.

    Analyzes data for common quality issues including duplicates,
    data type consistency, outliers, and completeness.
    """
    df = config.input_data
    logger.info(f"Assessing data quality: {df.shape}")

    quality_report = {
        'overall_score': 0.0,
        'checks': {},
        'summary': {
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'warnings': []
        },
        'recommendations': []
    }

    checks_performed = 0
    checks_passed = 0

    # Check for duplicates
    if config.check_duplicates:
        duplicate_count = df.duplicated().sum()
        duplicate_percentage = (duplicate_count / len(df)) * 100

        quality_report['checks']['duplicates'] = {
            'status': 'PASS' if duplicate_count == 0 else 'WARN',
            'duplicate_count': int(duplicate_count),
            'duplicate_percentage': float(duplicate_percentage),
            'message': f"{duplicate_count} duplicate rows found ({duplicate_percentage:.1f}%)"
        }

        checks_performed += 1
        if duplicate_count == 0:
            checks_passed += 1
        else:
            quality_report['recommendations'].append(
                "Consider removing duplicate rows to improve data quality"
            )

    # Check data types consistency
    if config.check_data_types:
        type_issues = []
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if numeric data is stored as strings
                try:
                    pd.to_numeric(df[col].dropna(), errors='raise')
                    type_issues.append(f"Column '{col}' contains numeric data stored as text")
                except:
                    pass

        quality_report['checks']['data_types'] = {
            'status': 'PASS' if not type_issues else 'WARN',
            'issues': type_issues,
            'message': f"{len(type_issues)} data type issues found"
        }

        checks_performed += 1
        if not type_issues:
            checks_passed += 1
        else:
            quality_report['recommendations'].extend([
                f"Consider converting {issue}" for issue in type_issues
            ])

    # Check for outliers
    if config.check_outliers:
        outlier_summary = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0 and col_data.std() > 0:
                z_scores = np.abs((col_data - col_data.mean()) / col_data.std())
                outlier_count = (z_scores > config.outlier_threshold).sum()
                outlier_percentage = (outlier_count / len(col_data)) * 100

                outlier_summary[col] = {
                    'outlier_count': int(outlier_count),
                    'outlier_percentage': float(outlier_percentage)
                }

        total_outliers = sum(info['outlier_count'] for info in outlier_summary.values())

        quality_report['checks']['outliers'] = {
            'status': 'PASS' if total_outliers == 0 else 'WARN',
            'total_outliers': int(total_outliers),
            'by_column': outlier_summary,
            'message': f"{total_outliers} outliers detected across {len(outlier_summary)} numeric columns"
        }

        checks_performed += 1
        if total_outliers == 0:
            checks_passed += 1
        else:
            quality_report['recommendations'].append(
                f"Review and potentially remove {total_outliers} outlier values"
            )

    # Calculate overall quality score
    quality_score = (checks_passed / checks_performed) * 100 if checks_performed > 0 else 0

    quality_report['overall_score'] = float(quality_score)
    quality_report['summary'].update({
        'total_checks': checks_performed,
        'passed_checks': checks_passed,
        'failed_checks': checks_performed - checks_passed
    })

    # Add summary recommendations
    if quality_score >= 90:
        quality_report['summary']['warnings'].append("Excellent data quality")
    elif quality_score >= 70:
        quality_report['summary']['warnings'].append("Good data quality with minor issues")
    elif quality_score >= 50:
        quality_report['summary']['warnings'].append("Moderate data quality - improvements recommended")
    else:
        quality_report['summary']['warnings'].append("Poor data quality - significant improvements needed")

    logger.info(f"Data quality assessment complete: {quality_score:.1f}% score")
    return quality_report