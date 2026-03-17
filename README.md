# Nexus

Nexus is a modern, extensible, file-based data processing framework designed for creating, managing, and executing complex data pipelines. It is built in Python and emphasizes a modular, plugin-driven architecture, and a streamlined command-line interface (CLI).

## Core Concepts

Nexus is built around a few core concepts:

*   **Pipelines:** The fundamental unit of execution in Nexus. A pipeline is a sequence of steps, defined in a YAML file, that process data.
*   **Plugins:** The building blocks of pipelines. A plugin is a Python function that performs a specific task. Nexus provides a simple decorator-based system for creating and registering plugins.
*   **Cases:** A case represents a specific scenario or dataset for a pipeline run. It's a directory that contains a `case.yaml` file defining the pipeline, along with any other necessary data or configuration.
*   **Templates:** Templates allow you to define reusable pipeline configurations that can be applied to multiple cases.

## Installation

1.  **Prerequisites:** Nexus requires Python 3.9 or higher.

2.  **Installation:** Clone the repository and install the project in editable mode with development dependencies:

    ```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

## Configuration

Nexus uses a hierarchical configuration system based on YAML files located in `config`:

* `config/setting.yaml`: System settings (framework paths, performance, logging).
* `config/setting-local.yaml`: Machine-specific overrides for system settings (git-ignored).
Precedence:
- System config: CLI `--config framework.* / logging.*` > `setting-local.yaml` > `setting.yaml`.
- Business config: CLI `--config plugins.*` > case/template (`case.yaml` or template) > plugin model defaults.

## Directory Structure

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

## Usage (CLI)

Nexus provides a powerful command-line interface, `nexus`, for interacting with the framework.

### Running Pipelines

The `run` command executes a pipeline for a specific case.

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

### Executing a Single Plugin

The `exec` command allows you to run a single plugin in the context of a case.

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

### Managing Plugins

The `plugins` command group provides tools for managing and inspecting plugins.

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

### Managing Cases and Templates

Nexus also provides commands for listing and inspecting cases and templates.

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

### Generating Documentation

The `doc` command generates markdown documentation for all registered plugins.

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

## Creating a Plugin

Creating a plugin in Nexus is straightforward:

1.  **Define a function:** Write a Python function that takes a `Context` object and a Pydantic model for configuration.
2.  **Add the `@plugin` decorator:** Decorate your function with `@plugin` from `nexus.core.discovery`.
3.  **Specify metadata:** Provide a `name`, an optional `config` model (a Pydantic class), and a `description` for your plugin.
4.  **Enable discovery:** Add the path to your plugin's package to the `framework.packages` list in `config/global.yaml`.

**Example:**

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

## Running Tests

Tests are written using `pytest`. To run the test suite:

```
nexus/
├── cases/                # Pipeline execution cases
├── config/               # System (setting*) and business (global) configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

