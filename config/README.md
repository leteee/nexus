# Configuration Files

This directory contains various configuration files for the Nexus project.

## Files

### development.yaml
Development environment configuration

### production.yaml
Production environment configuration (template)

### logging.yaml
Logging configuration for different environments

## Usage

Configuration files follow Vibecode principles:
- Clear, descriptive naming
- Environment-specific settings
- Secure defaults
- Well-documented options

Load configuration in your code:

```python
import yaml
from pathlib import Path

def load_config(env: str = "development") -> dict:
    """Load configuration for specified environment."""
    config_path = Path(__file__).parent / f"{env}.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
```