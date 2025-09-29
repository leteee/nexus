# Documentation Index

Welcome to the Nexus framework documentation. This index helps you find the information you need.

## Quick Start

- **[README.md](../README.md)** - Start here for installation and basic usage
- **[Configuration Examples](configuration-examples.md)** - Ready-to-use configuration templates

## Core Documentation

### Architecture & Design

- **[Architecture Design](architecture.md)** - Framework architecture, design principles, and patterns
  - Core principles and data_replay inspiration
  - Component architecture and data flow
  - Type safety and extensibility design

### Development Guides

- **[Plugin Development Guide](plugin-development.md)** - Complete guide to creating plugins
  - Plugin structure and configuration
  - Data source/sink annotations
  - Testing and best practices
  - Advanced features and patterns

### Reference

- **[API Reference](api-reference.md)** - Complete API documentation
  - Core functions and classes
  - Configuration schemas
  - CLI interface
  - Error handling

- **[Configuration Examples](configuration-examples.md)** - Comprehensive configuration examples
  - Basic to advanced configurations
  - Plugin configuration patterns
  - Environment-specific setups
  - Multi-source data integration

## Documentation by Use Case

### Getting Started
1. Read the [README.md](../README.md) for installation
2. Check [Configuration Examples](configuration-examples.md) for basic setup
3. Try the built-in plugins with `nexus list` and `nexus run`

### Building Data Pipelines
1. Study [Configuration Examples](configuration-examples.md) for pipeline patterns
2. Review [Architecture Design](architecture.md) for data flow concepts
3. Use [API Reference](api-reference.md) for programmatic usage

### Developing Custom Plugins
1. Follow the [Plugin Development Guide](plugin-development.md)
2. Reference [API Reference](api-reference.md) for class interfaces
3. Study [Architecture Design](architecture.md) for design patterns

### Advanced Usage
1. Understand [Architecture Design](architecture.md) for framework internals
2. Use [API Reference](api-reference.md) for advanced customization
3. Apply patterns from [Configuration Examples](configuration-examples.md)

## Framework Concepts

### Core Concepts Explained

| Concept | Description | Documentation |
|---------|-------------|---------------|
| **Immutable Contexts** | Frozen dataclasses prevent accidental state mutations | [Architecture](architecture.md#context-system) |
| **Functional Configuration** | Pure functions with caching for configuration management | [Architecture](architecture.md#configuration-system) |
| **Plugin Discovery** | Automatic registration and dependency resolution | [Plugin Guide](plugin-development.md#plugin-registration) |
| **Type Safety** | Comprehensive type hints and runtime validation | [API Reference](api-reference.md#type-annotations) |
| **Data Flow** | Declarative data source and sink annotations | [Plugin Guide](plugin-development.md#configuration-system) |
| **Hierarchical Config** | CLI > Case > Global > Plugin configuration precedence | [Config Examples](configuration-examples.md#basic-configuration) |

### Key Components

| Component | Purpose | Documentation |
|-----------|---------|---------------|
| **PipelineEngine** | Orchestrates complete pipeline lifecycle | [API Reference](api-reference.md#pipelineengine) |
| **DataHub** | Centralized data management with lazy loading | [API Reference](api-reference.md#datahub) |
| **Plugin System** | Decorator-based plugin registration | [Plugin Guide](plugin-development.md#quick-start) |
| **Configuration System** | Hierarchical configuration merging | [Architecture](architecture.md#configuration-system) |
| **Data Handlers** | Protocol-based data I/O operations | [API Reference](api-reference.md#data-handlers) |

## Examples by Complexity

### Beginner
- [Basic Configuration](configuration-examples.md#basic-configuration)
- [Simple Plugin Creation](plugin-development.md#basic-plugin-structure)
- [CLI Usage](../README.md#basic-usage)

### Intermediate
- [Advanced Analytics Pipeline](configuration-examples.md#advanced-analytics-case)
- [Plugin Configuration](plugin-development.md#configuration-system)
- [Data Source Management](configuration-examples.md#data-source-configuration)

### Advanced
- [Multi-Source Integration](configuration-examples.md#multi-source-data-integration)
- [Custom Data Handlers](plugin-development.md#custom-data-handlers)
- [Framework Extension](architecture.md#extensibility)

## Common Tasks

### Configuration Tasks
- **Setting up a new case**: [Case Configurations](configuration-examples.md#case-configurations)
- **Configuring data sources**: [Data Source Configuration](configuration-examples.md#data-source-configuration)
- **Environment-specific settings**: [Environment Configuration](configuration-examples.md#environment-specific-configuration)

### Development Tasks
- **Creating a new plugin**: [Plugin Development Guide](plugin-development.md#quick-start)
- **Testing plugins**: [Plugin Testing](plugin-development.md#testing-plugins)
- **Custom data formats**: [Custom Data Handlers](plugin-development.md#custom-data-handlers)

### Operations Tasks
- **Running pipelines**: [CLI Interface](api-reference.md#cli-interface)
- **Monitoring execution**: [Architecture Design](architecture.md#error-handling)
- **Debugging issues**: [Plugin Development Guide](plugin-development.md#troubleshooting)

## FAQ Quick Links

**Q: How do I create my first plugin?**
A: Start with the [Basic Plugin Structure](plugin-development.md#basic-plugin-structure) in the Plugin Development Guide.

**Q: How does configuration precedence work?**
A: Check the [Configuration System](architecture.md#configuration-system) section in Architecture Design.

**Q: How do I handle different data formats?**
A: See [Data Source Configuration](configuration-examples.md#file-based-data-sources) and [Custom Data Handlers](plugin-development.md#custom-data-handlers).

**Q: How do I test my plugins?**
A: Follow the [Testing Plugins](plugin-development.md#testing-plugins) section in the Plugin Development Guide.

**Q: How do I set up environment-specific configurations?**
A: Review [Environment-Specific Configuration](configuration-examples.md#environment-specific-configuration).

## Contributing to Documentation

When contributing to Nexus documentation:

1. **Update this index** when adding new documentation files
2. **Cross-reference** related concepts between documents
3. **Include examples** for all new features or APIs
4. **Test examples** to ensure they work with current framework version
5. **Follow Markdown standards** for consistency

## Documentation Standards

- Use clear, concise language
- Provide working code examples
- Include error handling in examples
- Reference related concepts with links
- Keep examples up-to-date with latest API

## Version Information

This documentation corresponds to Nexus framework version 0.2.0.

For the latest updates and changes, see the project [README.md](../README.md) and check the Git history for recent modifications.