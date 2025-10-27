"""
Built-in plugin package demonstrating the sideloading pattern.

Structure:
  contrib/               <- Package root (sideloaded via global.yaml)
  ├── basic/             <- Business logic (framework-independent)
  │   ├── generation.py  <- Data generation utilities
  │   └── processing.py  <- Data processing utilities
  └── nexus/             <- Nexus adapters (framework-dependent)
      └── __init__.py    <- 5 @plugin decorators

This structure allows:
- contrib.basic can be used standalone (no nexus dependency)
- contrib.nexus is only imported when nexus discovers the package
- External packages can follow the same pattern
"""
