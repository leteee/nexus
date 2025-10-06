# Nexus Documentation

Welcome to Nexus - A modern, functional data processing framework.

---

## 📚 Documentation Guide

This guide helps you find the right documentation for your needs. Each document has a clear purpose and target audience.

---

## 🎯 By Role

### For New Users
Start here if you're new to Nexus:

1. **[Main README](../README.md)** - Installation, quick start, first examples
2. **[Example Cases](../cases/README.md)** - Ready-to-run examples to learn from
3. **[CLI Reference](cli-reference.md)** - Learn the basic commands
4. **[Execution Flows](execution-flows.md)** - Understand how Nexus works with diagrams

### For Pipeline Developers
Building data pipelines with Nexus:

1. **[Feature Guide](features.md)** - Complete feature overview and capabilities
2. **[Execution Flows](execution-flows.md)** - Detailed execution flow diagrams
3. **[Configuration Best Practices](configuration-best-practices.md)** - Advanced configuration patterns
4. **[CLI Reference](cli-reference.md)** - All commands and options
5. **[Example Cases](../cases/README.md)** - Real-world pipeline examples

### For Framework Developers
Extending or contributing to Nexus:

1. **[Architecture](architecture.md)** - Framework design, principles, and internals
2. **[Execution Flows](execution-flows.md)** - Detailed sequence diagrams
3. **[Feature Guide](features.md)** - Plugin system and extensibility points
4. **[Configuration Best Practices](configuration-best-practices.md)** - Configuration system deep dive

---

## 📖 By Document

### 📘 [Main README](../README.md)
**Purpose**: Getting started guide
**Audience**: New users
**Content**:
- Installation instructions
- Quick start tutorial
- Basic usage examples
- Project overview

**When to use**: You're installing Nexus for the first time or need a quick refresher.

---

### 📗 [Feature Guide](features.md)
**Purpose**: Comprehensive feature documentation
**Audience**: Pipeline developers
**Content**:
- Plugin system overview
- Configuration management
- Data handling features
- Template system
- Case management
- All framework capabilities

**When to use**: You need to understand what Nexus can do and how to use specific features.

---

### 📙 [CLI Reference](cli-reference.md)
**Purpose**: Command-line interface documentation
**Audience**: All users
**Content**:
- Complete command reference
- All options and flags
- Usage examples for each command
- Command patterns and conventions

**When to use**: You need syntax help for CLI commands or want to discover available options.

---

### 📕 [Execution Flows](execution-flows.md)
**Purpose**: Visual execution flow documentation
**Audience**: Pipeline developers, framework developers
**Content**:
- Sequence diagrams for single plugin execution
- Sequence diagrams for full pipeline execution
- Configuration resolution flow
- Data flow diagrams
- Error handling flows

**When to use**: You need to understand how Nexus executes pipelines internally, or you're debugging execution issues.

---

### 📓 [Configuration Best Practices](configuration-best-practices.md)
**Purpose**: Advanced configuration patterns and practices
**Audience**: Experienced pipeline developers
**Content**:
- Configuration hierarchy in depth
- Plugin configuration patterns
- Environment-specific configurations
- Security best practices
- Performance optimization
- Reusable configuration strategies

**When to use**: You're building complex pipelines and need advanced configuration techniques.

---

### 📔 [Architecture](architecture.md)
**Purpose**: Framework design and internals
**Audience**: Framework developers, contributors
**Content**:
- Design philosophy and principles
- Component architecture
- Design patterns used
- Type safety approach
- Performance considerations
- Security design
- Testing strategy

**When to use**: You want to understand Nexus internals, extend the framework, or contribute to development.

---

### 📒 [Example Cases](../cases/README.md)
**Purpose**: Ready-to-run example pipelines
**Audience**: All users
**Content**:
- Quickstart example
- Pipeline flow example
- Multi-output example
- Hybrid paths example
- Complete case configurations
- Expected outputs

**When to use**: You want to see working examples or need a starting point for your own pipeline.

---

## 🔍 By Topic

### Installation & Setup
- [Main README → Installation](../README.md#installation)
- [Main README → Quick Start](../README.md#quick-start)

### Running Pipelines
- [CLI Reference → nexus run](cli-reference.md#nexus-run)
- [Execution Flows → Full Pipeline Execution](execution-flows.md#full-pipeline-execution)
- [Example Cases](../cases/README.md)

### Running Individual Plugins
- [CLI Reference → nexus plugin](cli-reference.md#nexus-plugin)
- [Execution Flows → Single Plugin Execution](execution-flows.md#single-plugin-execution)

### Configuration
- [Feature Guide → Configuration Management](features.md#configuration-management)
- [Configuration Best Practices](configuration-best-practices.md)
- [Execution Flows → Configuration Resolution](execution-flows.md#configuration-resolution)

### Plugin Development
- [Feature Guide → Plugin System](features.md#plugin-system)
- [Architecture → Plugin System](architecture.md#3-plugin-system)
- [Configuration Best Practices → Plugin Configuration](configuration-best-practices.md#plugin-configuration-patterns)

### Data Handling
- [Feature Guide → Data Management](features.md#data-management)
- [Architecture → Data Management](architecture.md#4-data-management)
- [Execution Flows → Data Flow](execution-flows.md#data-flow)

### Templates & Cases
- [Feature Guide → Templates](features.md#templates)
- [CLI Reference → nexus init](cli-reference.md#nexus-init)
- [Example Cases](../cases/README.md)

### Troubleshooting
- [Execution Flows → Error Handling Flow](execution-flows.md#error-handling-flow)
- [Configuration Best Practices → Debugging](configuration-best-practices.md#debugging-configuration-issues)

---

## 🚀 Quick Start Paths

### "I want to run my first pipeline"
1. [Main README → Installation](../README.md#installation)
2. [Main README → Quick Start](../README.md#quick-start)
3. [Example Cases → Quickstart](../cases/README.md#quickstart)

### "I want to build a custom pipeline"
1. [Feature Guide](features.md)
2. [CLI Reference → nexus init](cli-reference.md#nexus-init)
3. [Configuration Best Practices](configuration-best-practices.md)
4. [Example Cases](../cases/README.md)

### "I want to develop a plugin"
1. [Feature Guide → Plugin System](features.md#plugin-system)
2. [Architecture → Plugin System](architecture.md#3-plugin-system)
3. [Configuration Best Practices → Plugin Configuration](configuration-best-practices.md#plugin-configuration-patterns)

### "I want to understand how it works"
1. [Architecture](architecture.md)
2. [Execution Flows](execution-flows.md)
3. [Feature Guide](features.md)

### "I want to contribute to Nexus"
1. [Architecture](architecture.md)
2. [Execution Flows](execution-flows.md)
3. [Main README → Development](../README.md#development)

---

## 📋 Documentation Principles

Our documentation follows these principles:

### 1. **Clear Separation of Concerns**
Each document has a single, well-defined purpose. No overlap or duplication.

### 2. **Progressive Disclosure**
Start simple, provide paths to deeper knowledge. Beginners aren't overwhelmed, experts can dive deep.

### 3. **Task-Oriented**
Organized by what you want to accomplish, not by implementation details.

### 4. **Visual When Helpful**
Sequence diagrams, flowcharts, and examples make complex concepts clear.

### 5. **Practical Examples**
Every concept includes working code examples you can run.

### 6. **Consistent Structure**
Similar documents follow similar patterns for easy navigation.

---

## 🆘 Need Help?

### Can't find what you need?
1. Check the [topic index](#by-topic) above
2. Use your browser's search function (Ctrl+F / Cmd+F)
3. Browse the [example cases](../cases/README.md)

### Found an issue?
- Documentation bugs: Open an issue
- Suggestions: Submit a pull request
- Questions: Check existing issues or create a new one

---

## 📈 Documentation Map

```
nexus/
├── README.md                          # Installation & Quick Start
├── docs/
│   ├── README.md                      # This file - Documentation guide
│   ├── features.md                    # Complete feature reference
│   ├── cli-reference.md               # CLI command reference
│   ├── execution-flows.md             # Execution flow diagrams (NEW!)
│   ├── configuration-best-practices.md # Advanced configuration
│   └── architecture.md                # Framework internals
└── cases/
    └── README.md                      # Example pipelines
```

---

**Last Updated**: 2025-01-XX
**Version**: 1.0.0
