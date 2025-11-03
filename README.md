# Nexus

A lightweight plugin orchestrator for Python scripts. Nexus focuses on three ideas:

- **Case-based workspaces**: each case directory contains data + configuration.
- **Template pipelines**: reusable YAML files describe which plugins to run.
- **Pure Python plugins**: plain functions decorated with `@plugin`, validated with Pydantic configs.

## Quick Start

```bash
pip install -e ".[dev]"

# List plugins/templates/cases
nexus list plugins
nexus list templates
nexus list cases

# Run a template-driven pipeline
nexus run --case quickstart --template quickstart
nexus run --case demo --template basic/demo

# Execute a single plugin
nexus plugin "Data Generator" --case demo --config num_rows=500
```

### Built-in templates

| Template | Description | Key plugins |
|----------|-------------|-------------|
| `quickstart` | Minimal single-step pipeline that generates synthetic data and optionally writes it to `data/` | `Data Generator` |
| `basic/demo` | Four-step in-memory demo: generate → filter → aggregate → validate | `Data Generator`, `Data Filter`, `Data Aggregator`, `Data Validator` |

## Writing Plugins

```python
import pandas as pd
from nexus.core.discovery import plugin
from nexus.core.types import PluginConfig

class CleanConfig(PluginConfig):
    drop_nulls: bool = True

@plugin(name="Clean Data", config=CleanConfig)
def clean_data(ctx):
    df = ctx.recall("last_result")
    if df is None:
        raise RuntimeError("Clean Data needs upstream results")
    if ctx.config.drop_nulls:
        df = df.dropna()
    ctx.remember("last_result", df)
    return df
```

Plugins receive a `PluginContext` with helpers:

- `ctx.config`: validated configuration model (or `None`).
- `ctx.logger`: project-aware logger.
- `ctx.resolve_path(str)`: resolve paths relative to the case directory.
- `ctx.remember(key, value)` / `ctx.recall(key)`: share state between steps.

## Pipeline Definition

`case.yaml` or template files describe the pipeline:

```yaml
case_info:
  name: "Quickstart"

pipeline:
  - plugin: "Data Generator"
    config:
      num_rows: 500
  - plugin: "Data Filter"
    config:
      column: "value"
      operator: ">"
      threshold: 100
```

Run it with `nexus run --case demo --template quickstart` or copy the YAML into `cases/demo/case.yaml`.

## Sideloading Plugins

1. Place your business logic in a standalone package (e.g., `alpha.logic`).
2. Add a `nexus/` package next to it that imports `nexus.plugin` and adapts the logic.
3. Point `framework.packages` to the parent directory (e.g., `D:/projects/nexus_workspace/alpha`).
4. Nexus discovery adds that directory to `sys.path` and imports the package, registering adapters just like the built-in `nexus.contrib.basic` module.

This means sidecar modules can run independently, yet seamlessly provide plugins when Nexus is in charge.


## Programmatic API

```python
from pathlib import Path
import nexus

case_path = "demo"
manager, _ = nexus._build_case_manager(Path.cwd())
config_path, case_config = manager.get_case_config(case_path)
engine = nexus.create_engine(case_path)
results = engine.run_pipeline(case_config)
```

## Why Nexus?

- Declarative pipeline descriptions with minimal boilerplate.
- Simple execution model: a shared in-memory state instead of hidden data hubs.
- Easy plugin authoring using plain Python and Pydantic validation.

## License

MIT License. See `LICENSE` for details.

