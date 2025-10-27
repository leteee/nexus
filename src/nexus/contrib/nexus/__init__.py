"""
Nexus plugin adapters entry point.

Imports all adapter modules to register plugins with Nexus discovery system.

Structure:
  - basic.py: Data generation and processing plugins (5 plugins)
  - repro.py: Video replay and data rendering plugins (3 plugins)
"""

# Import adapter modules to trigger plugin registration
from . import basic  # noqa: F401
from . import repro  # noqa: F401
