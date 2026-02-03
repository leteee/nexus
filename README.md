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

    ```bash
    git clone <repository-url>
    cd nexus
    pip install -e .[dev]
    ```

## Configuration

Nexus uses a hierarchical configuration system based on YAML files. Configuration files are located in the `config` directory:

*   `config/global.yaml`: The main configuration file for the project. It defines global settings such as plugin discovery paths and default configurations.
*   `config/local.yaml`: For local overrides. This file is not tracked by Git. You can create it by copying `config/local.yaml.example`.

The configuration is loaded in the following order, with later files overriding earlier ones:
1.  `config/global.yaml`
2.  `config/local.yaml`
3.  Case-specific configuration (`case.yaml`)
4.  Command-line overrides

## Directory Structure

```
nexus/
├── cases/                # Contains pipeline execution cases
├── config/               # Global and local configuration
├── src/
│   └── nexus/            # Main source code
│       ├── core/         # Core framework components (engine, config, etc.)
│       ├── contrib/      # Built-in plugins
│       └── cli.py        # Command-line interface definition
├── templates/            # Reusable pipeline templates
└── pyproject.toml        # Project metadata and dependencies
```

## Usage (CLI)

Nexus provides a powerful command-line interface, `nexus`, for interacting with the framework.

### Running Pipelines

The `run` command executes a pipeline for a specific case.

```bash
# Run the 'my_case' pipeline
nexus run --case my_case

# Run with a specific template
nexus run --case my_case --template data_analysis

# Override configuration values
nexus run --case my_case -C plugins.my_plugin.threshold=0.75
```

### Executing a Single Plugin

The `exec` command allows you to run a single plugin in the context of a case.

```bash
# Execute the 'my-plugin' in the context of 'my_case'
nexus exec my-plugin --case my_case
```

### Managing Plugins

The `plugins` command group provides tools for managing and inspecting plugins.

```bash
# List all available plugins
nexus plugins list

# Show detailed information about a plugin, including its configuration
nexus plugins show my-plugin

# Search for plugins by keyword
nexus plugins search video

# List all plugin tags
nexus plugins tags
```

### Managing Cases and Templates

Nexus also provides commands for listing and inspecting cases and templates.

```bash
# List all available cases
nexus cases list

# List all available templates
nexus templates list
```

### Generating Documentation

The `doc` command generates markdown documentation for all registered plugins.

```bash
# Generate plugin documentation in the 'docs/api' directory
nexus doc --output docs/api
```

## Creating a Plugin

Creating a plugin in Nexus is straightforward:

1.  **Define a function:** Write a Python function that takes a `Context` object and a Pydantic model for configuration.
2.  **Add the `@plugin` decorator:** Decorate your function with `@plugin` from `nexus.core.discovery`.
3.  **Specify metadata:** Provide a `name`, an optional `config` model (a Pydantic class), and a `description` for your plugin.
4.  **Enable discovery:** Add the path to your plugin's package to the `framework.packages` list in `config/global.yaml`.

**Example:**

```python
# In my_plugins/my_plugin.py
from pydantic import BaseModel, Field
from nexus.core.discovery import plugin
from nexus.core.context import Context

class MyPluginConfig(BaseModel):
    my_parameter: str = Field("default_value", description="An example parameter.")

@plugin(
    name="my-plugin",
    config=MyPluginConfig,
    description="A simple example plugin."
)
def my_plugin(ctx: Context, config: MyPluginConfig):
    """
    This is my first Nexus plugin.
    """
    ctx.log.info(f"Running my-plugin with parameter: {config.my_parameter}")
    # ... plugin logic ...
```

## Running Tests

Tests are written using `pytest`. To run the test suite:

```bash
pytest
```