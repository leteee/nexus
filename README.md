# Nexus

A modern Python project following Vibecode best practices.

## Overview

Nexus demonstrates contemporary Python development practices including:
- Clean, readable code structure
- Type hints and documentation
- Comprehensive testing setup
- Code quality tools (linting, formatting)
- Modern dependency management with pyproject.toml

## Features

- **Vibecode Principles**: Natural language-friendly development approach
- **Modern Python**: Support for Python 3.9+
- **Quality Tools**: Black, isort, flake8, mypy integration
- **Testing**: pytest with coverage reporting
- **Pre-commit hooks**: Automated code quality checks

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nexus.git
cd nexus

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
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
# Run tests
pytest

# Run tests with coverage
pytest --cov=src/nexus --cov-report=html
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Project Structure

```
nexus/
├── src/nexus/          # Main package source code
├── tests/              # Test files
├── docs/               # Documentation
├── config/             # Configuration files
├── scripts/            # Utility scripts
├── pyproject.toml      # Project configuration and dependencies
├── README.md           # This file
└── LICENSE             # MIT License
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and quality checks
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.