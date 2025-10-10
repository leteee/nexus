# Nexus Documentation

Welcome to Nexus - A modern, functional data processing framework.

---

## 📚 Documentation Guide

### Quick Start Path

**New to Nexus?** Follow this path:
1. **[Main README](../README.md)** - Installation & quick start
2. **[User Guide](user-guide.md)** - Complete usage guide
3. **[Example Cases](../cases/README.md)** - Ready-to-run examples

---

## 📖 Core Documentation

### 📘 [User Guide](user-guide.md)
**Complete usage documentation**

**What's inside**:
- Quick start tutorial
- All CLI commands with examples
- Configuration system
- Built-in plugins reference
- Creating custom plugins
- Best practices & tips

**When to read**: You're learning Nexus or need command/feature reference.

**Length**: ~685 lines (comprehensive but focused)

---

### 📗 [Architecture](architecture.md)
**Framework design and internals**

**What's inside**:
- Design philosophy and principles
- Component architecture
- Plugin system internals
- Data management design
- Performance considerations
- Security design

**When to read**: You want to extend Nexus or contribute to development.

**Length**: ~470 lines (technical depth)

---

### 📙 [Execution Flows](execution-flows.md)
**Visual execution flow documentation**

**What's inside**:
- Pipeline execution diagrams
- Single plugin execution flow
- Configuration resolution flow
- Data flow diagrams
- Error handling flows

**When to read**: You need to understand how Nexus works internally or debug issues.

**Length**: ~556 lines (visual diagrams)

---

### 📕 [Example Cases](../cases/README.md)
**Ready-to-run examples**

**What's inside**:
- **quickstart** - Minimal single-plugin example
- **demo** - Comprehensive 4-step pipeline (Generate → Filter → Aggregate → Validate)

**When to read**: You want working examples to learn from.

---

### 📓 [API Documentation](api/README.md)
**Auto-generated plugin and handler docs**

**What's inside**:
- 5 plugin specifications
- 6 handler specifications
- Configuration schemas
- Usage examples

**When to read**: You need detailed plugin/handler reference.

**How to generate**: Run `nexus doc --force`

---

### 📔 [Documentation Design](documentation-design.md)
**Documentation generation design and best practices**

**What's inside**:
- Documentation design principles (DRY, YAGNI, Practical First)
- Plugin API documentation format and evolution
- Implementation details of `nexus doc` command
- CLI help system design decisions
- Best practices for maintaining documentation

**When to read**: You're working on documentation generation or want to understand design decisions.

**Length**: ~560 lines (comprehensive meta-documentation)

---

## 🎯 By Task

### Running Pipelines
- [User Guide → nexus run](user-guide.md#nexus-run)
- [Example Cases](../cases/README.md)

### Running Single Plugins
- [User Guide → nexus plugin](user-guide.md#nexus-plugin)
- [User Guide → Built-in Plugins](user-guide.md#built-in-plugins)

### Configuration
- [User Guide → Configuration System](user-guide.md#configuration-system)
- [User Guide → Configuration Overrides](user-guide.md#configuration-overrides)

### Creating Plugins
- [User Guide → Creating Custom Plugins](user-guide.md#creating-custom-plugins)
- [Architecture → Plugin System](architecture.md#3-plugin-system)

### Understanding Framework
- [Architecture](architecture.md)
- [Execution Flows](execution-flows.md)

---

## 🚀 Learning Paths

### "I want to use Nexus"
1. Read [Main README](../README.md)
2. Run [Example Cases](../cases/README.md)
3. Reference [User Guide](user-guide.md)

### "I want to build custom pipelines"
1. Read [User Guide → CLI Commands](user-guide.md#cli-commands)
2. Study [User Guide → Pipeline Definition](user-guide.md#pipeline-definition)
3. Try [Example Cases → demo](../cases/README.md#demo)

### "I want to create plugins"
1. Read [User Guide → Creating Custom Plugins](user-guide.md#creating-custom-plugins)
2. Study [Architecture → Plugin System](architecture.md#3-plugin-system)
3. Review [Built-in Plugins](user-guide.md#built-in-plugins) for examples

### "I want to understand internals"
1. Read [Architecture](architecture.md)
2. Study [Execution Flows](execution-flows.md)
3. Explore source code in `src/nexus/`

### "I want to contribute"
1. Read [Architecture](architecture.md)
2. Study [Execution Flows](execution-flows.md)
3. Check [Main README → Development](../README.md#development)

---

## 📈 Documentation Structure

```
nexus/
├── README.md                    # Installation & quick start
├── docs/
│   ├── README.md               # This file - Documentation index
│   ├── user-guide.md           # Complete usage guide
│   ├── architecture.md         # Framework design & internals
│   ├── execution-flows.md      # Visual flow diagrams
│   ├── documentation-design.md # Documentation generation design
│   └── api/                    # Auto-generated API docs
│       ├── README.md
│       ├── plugins/            # Plugin documentation
│       └── handlers/           # Handler documentation
└── cases/
    ├── README.md               # Example cases index
    ├── quickstart/             # Minimal example
    └── demo/                   # Comprehensive pipeline
```

---

## 📋 Documentation Principles

### 1. **No Redundancy**
Each document has a single, well-defined purpose. No overlap or duplication.

### 2. **Progressive Disclosure**
Start simple (User Guide), dive deep when needed (Architecture).

### 3. **Task-Oriented**
Organized by what you want to accomplish, not implementation details.

### 4. **Practical Examples**
Every concept includes working code examples.

### 5. **Visual When Helpful**
Diagrams and flowcharts make complex concepts clear (Execution Flows).

### 6. **Auto-Generated Documentation**
API documentation is auto-generated using `nexus doc` command following DRY principles.
See [Documentation Design](documentation-design.md) for design rationale and best practices.

---

## 🆘 Quick Reference

| I need... | Go to... |
|-----------|----------|
| Install Nexus | [Main README](../README.md) |
| Learn CLI commands | [User Guide → CLI Commands](user-guide.md#cli-commands) |
| See examples | [Example Cases](../cases/README.md) |
| Plugin reference | [User Guide → Built-in Plugins](user-guide.md#built-in-plugins) |
| Create custom plugin | [User Guide → Creating Custom Plugins](user-guide.md#creating-custom-plugins) |
| Understand config | [User Guide → Configuration System](user-guide.md#configuration-system) |
| Framework internals | [Architecture](architecture.md) |
| Execution flow | [Execution Flows](execution-flows.md) |
| API reference | [API Documentation](api/README.md) |
| Documentation design | [Documentation Design](documentation-design.md) |

---

## 📊 Documentation Stats

- **Total lines**: ~2,543 (includes new documentation-design.md)
- **Core documents**: 5 (user-guide, architecture, execution-flows, documentation-design, README)
- **Example cases**: 2 (quickstart, demo)
- **Plugins documented**: 5
- **Handlers documented**: 6

---

**Last Updated**: 2025-01-10
**Version**: 1.1.0
