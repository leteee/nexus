# Development Scripts

This directory contains utility scripts for development workflow.

## Available Scripts

### setup.py
Initial project setup script that:
- Installs development dependencies
- Sets up pre-commit hooks
- Runs initial code quality checks

### quality.py
Code quality checking script that runs:
- Black (code formatting)
- isort (import sorting)
- flake8 (linting)
- mypy (type checking)

### test.py
Testing utilities script that:
- Runs pytest with coverage
- Generates coverage reports
- Validates test quality

## Usage

```bash
# Run setup script
python scripts/setup.py

# Check code quality
python scripts/quality.py

# Run comprehensive tests
python scripts/test.py
```