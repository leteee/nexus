# Nexus Documentation

Welcome to Nexus - A modern, functional data processing framework.

---

## 📚 Documentation Index

### Getting Started

- **[Main README](../README.md)** - Installation, quick start, basic usage
- **[Feature Guide](features.md)** - Complete feature overview and capabilities
- **[CLI Reference](cli-reference.md)** - All CLI commands and options
- **[Example Cases](../cases/README.md)** - Ready-to-run examples

### Architecture & Design

- **[Architecture](architecture.md)** - Framework design, principles, and internals
- **[Configuration Best Practices](configuration-best-practices.md)** - Advanced configuration patterns

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install -e .
```

### 2. Run Example
```bash
nexus run --case quickstart
```

### 3. List Plugins
```bash
nexus list plugins
```

---

## 📖 Documentation by Task

### Running Pipelines

**Goal**: Execute data pipelines

1. **[CLI Reference → nexus run](cli-reference.md#nexus-run)** - Command syntax
2. **[Example Cases](../cases/README.md)** - Ready-to-run examples
3. **[Feature Guide → Pipeline Execution](features.md#pipeline-execution)** - How pipelines work

### Using Plugins

**Goal**: Execute individual plugins

1. **[CLI Reference → nexus plugin](cli-reference.md#nexus-plugin)** - Command syntax
2. **[Feature Guide → Built-in Plugins](features.md#built-in-plugins)** - Available plugins
3. **[Feature Guide → Smart Discovery](features.md#4-smart-data-discovery-)** - Auto data discovery

### Configuration

**Goal**: Configure pipelines and plugins

1. **[Feature Guide → Configuration System](features.md#configuration-system)** - Overview
2. **[Configuration Best Practices](configuration-best-practices.md)** - Patterns and tips
3. **[Feature Guide → Path Resolution](features.md#path-resolution)** - Path strategies

### Development

**Goal**: Create custom plugins

1. **[Feature Guide → Custom Plugins](features.md#custom-plugins)** - Plugin development
2. **[Architecture](architecture.md)** - Framework internals
3. **[Feature Guide → Custom Handlers](features.md#custom-data-handlers)** - Extend I/O

---

## 🎯 Core Concepts

### Hybrid Path Resolution ⭐

Three ways to reference data:

```yaml
"@customer_master"    # Explicit logical name (recommended)
"customer_master"     # Implicit logical name (auto-detected)
"data/file.csv"       # Direct path
```

**Learn more**: [Feature Guide → Path Resolution](features.md#path-resolution)

---

### Automatic I/O Handling 🔄

Framework automatically loads inputs and saves outputs:

```python
class MyConfig(PluginConfig):
    input_data: Annotated[str, DataSource(...)] = "input.csv"
    output_data: Annotated[str, DataSink(...)] = "output.parquet"

@plugin(name="My Plugin", config=MyConfig)
def my_plugin(ctx):
    df = ctx.datahub.get("input_data")  # Auto-loaded
    return df.processed()                # Auto-saved
```

**Learn more**: [Feature Guide → Automatic I/O](features.md#2-automatic-io-handling-)

---

### Configuration Hierarchy 📊

Precedence: **CLI > Case > Global > Plugin Defaults**

```bash
nexus run -c my-case -C num_rows=5000
#                    ↑ Overrides everything
```

**Learn more**: [Feature Guide → Configuration](features.md#hierarchical-configuration)

---

## 📋 CLI Command Reference

### nexus run
Execute complete pipeline from `case.yaml`

```bash
nexus run --case CASE [--config key=value]
```

### nexus plugin
Execute single plugin with auto-discovery

```bash
nexus plugin "PLUGIN_NAME" --case CASE [--config key=value]
```

### nexus list
List resources (plugins, cases, templates)

```bash
nexus list [plugins|cases|templates]
```

**Full Reference**: [CLI Reference](cli-reference.md)

---

## 🏗️ Architecture Overview

### Core Components

| Component | Purpose |
|-----------|---------|
| **PipelineEngine** | Orchestrates pipeline execution |
| **DataHub** | Manages data with lazy loading & caching |
| **Plugin System** | Decorator-based plugin registration |
| **Config System** | Hierarchical configuration merging |

**Learn more**: [Architecture](architecture.md)

---

### Design Principles

- ✅ **Immutability** - Frozen contexts prevent side effects
- ✅ **Functional** - Pure functions with caching
- ✅ **Type Safety** - Comprehensive type hints + runtime validation
- ✅ **Declarative** - YAML configuration + Python annotations

**Learn more**: [Architecture → Design Philosophy](architecture.md#design-philosophy)

---

## 📦 Built-in Features

### Data Management
- ✅ Multiple format support (CSV, JSON, Parquet, Excel, XML)
- ✅ Lazy loading with automatic caching
- ✅ Type validation
- ✅ Custom handler extensibility

### Plugin System
- ✅ Auto-discovery and registration
- ✅ Type-safe configuration (Pydantic)
- ✅ Single and multi-output support
- ✅ Immutable execution context

### Path Resolution
- ✅ Explicit logical names (`@name`)
- ✅ Implicit logical names (`name`)
- ✅ Direct paths (`path/file`)
- ✅ Global data source registry

**Full Feature List**: [Feature Guide](features.md)

---

## 🎓 Learning Path

### Beginner (30 minutes)

1. Read [Main README](../README.md) - Installation & basics
2. Run `nexus run --case quickstart` - First pipeline
3. Explore [Example Cases](../cases/README.md) - Learn by example
4. Try `nexus plugin "Data Generator" -c test` - Single plugin

### Intermediate (1 hour)

1. Study [Feature Guide](features.md) - All capabilities
2. Read [CLI Reference](cli-reference.md) - All commands
3. Practice with `hybrid-paths` case - Path strategies
4. Practice with `pipeline-flow` case - Multi-step pipelines

### Advanced (2 hours)

1. Read [Architecture](architecture.md) - Framework internals
2. Study [Configuration Best Practices](configuration-best-practices.md) - Advanced patterns
3. Create custom plugin - [Feature Guide → Custom Plugins](features.md#custom-plugins)
4. Extend with custom handler - [Feature Guide → Custom Handlers](features.md#custom-data-handlers)

---

## 💡 Quick Tips

### Run Pipeline
```bash
nexus run --case quickstart
```

### Generate Test Data
```bash
nexus plugin "Data Generator" -c test -C num_rows=1000
```

### Override Configuration
```bash
nexus run -c my-case -C num_rows=5000 -C output_data=data/custom.csv
```

### List Everything
```bash
nexus list plugins
nexus list cases
nexus list templates
```

### Verbose Logging
```bash
nexus run -c my-case -v
```

---

## 🔗 External Resources

- **GitHub**: [Project Repository](https://github.com/your-org/nexus)
- **Issues**: [Report Bugs](https://github.com/your-org/nexus/issues)
- **Discussions**: [Community Forum](https://github.com/your-org/nexus/discussions)

---

## 📄 Document Reference

| Document | Purpose | Audience |
|----------|---------|----------|
| [Main README](../README.md) | Installation & quick start | Everyone |
| [Feature Guide](features.md) | Complete feature overview | Users |
| [CLI Reference](cli-reference.md) | CLI command reference | Users |
| [Example Cases](../cases/README.md) | Working examples | Users |
| [Configuration Best Practices](configuration-best-practices.md) | Advanced config patterns | Advanced Users |
| [Architecture](architecture.md) | Framework internals | Developers |

---

## 🆘 Getting Help

### Common Questions

**Q: How do I run my first pipeline?**
```bash
nexus run --case quickstart
```

**Q: How do I create a plugin?**
See [Feature Guide → Custom Plugins](features.md#custom-plugins)

**Q: How does path resolution work?**
See [Feature Guide → Path Resolution](features.md#path-resolution)

**Q: How do I override configuration?**
See [CLI Reference → Configuration Overrides](cli-reference.md#configuration-overrides)

### Need Help?

1. Check [CLI Reference](cli-reference.md) for command syntax
2. Browse [Example Cases](../cases/README.md) for patterns
3. Read [Feature Guide](features.md) for capabilities
4. Open an [Issue](https://github.com/your-org/nexus/issues) if stuck

---

## 📝 Contributing

To contribute documentation:

1. **Keep it current** - Test all examples
2. **Be clear** - Use simple language
3. **Show examples** - Code speaks louder
4. **Cross-reference** - Link related concepts
5. **Update index** - Add new docs here

---

## Version

**Documentation Version**: 0.2.0
**Last Updated**: 2025-01-05

*This documentation reflects the latest framework capabilities including the hybrid path resolution system.*
