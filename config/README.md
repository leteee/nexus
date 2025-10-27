# Configuration Directory

Nexus configuration files for framework settings and plugin defaults.

## Files

### `global.yaml`
Framework-wide defaults (version controlled).

Key sections:
- `framework.cases_roots` - Where to find case directories
- `framework.templates_roots` - Where to find template files
- `framework.packages` - Plugin discovery paths
- `plugins.*` - Default configuration for all plugins

### `local.yaml` (gitignored)
User-specific overrides merged with global.yaml.

Create from example:
```bash
cp local.yaml.example local.yaml
```

Use for:
- Sideloading external plugin packages
- Local logging levels
- Development-specific settings

### `local.yaml.example`
Template showing how to configure local overrides.

## Configuration Hierarchy

From highest to lowest precedence:

1. **CLI overrides** - `--config key=value`
2. **Case/Template** - `case.yaml` or template YAML
3. **Local config** - `local.yaml` (merged with global)
4. **Global config** - `global.yaml`
5. **Plugin defaults** - From `PluginConfig` classes

## Sideloading Plugins

Add external plugin packages in `local.yaml`:

```yaml
framework:
  packages:
    - "path/to/your_package"
```

Required structure:
```
your_package/
├── submodule/      # Business logic (no nexus dependency)
└── nexus/          # Adapters (@plugin decorators)
    └── __init__.py
```

See `local.yaml.example` for detailed examples.
