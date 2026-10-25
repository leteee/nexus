# Nexus

**A configurable, orchestratable Python logic execution engine.**
Current release: **2.0.0**.

Nexus keeps *logic* in Python and *composition* in configuration. Small Python
functions are registered as **nodes**; flows assemble those nodes in YAML with
typed inputs, DAG dependencies, conditions, loops, retries, timeouts, subflows
and parallel execution.

Nexus runs locally as a library and CLI; the core has no service dependency.

- **Declarative composition.** Flows are data; no code generation and no
  framework imports inside flow files.
- **Typed contracts.** Nodes declare Pydantic input models; invalid
  configuration fails before the node runs.
- **Explicit data flow.** Steps exchange values through `${steps.<id>...}`
  expressions rather than hidden mutable state.
- **DAG + control flow.** Dependencies, parallel branches, conditions,
  `foreach`, retries, timeouts, error policies and subflows.
- **Extensible.** General-purpose nodes live in the core; domain logic lives in
  separate packages loaded through `node_modules` or entry points.

## Installation

Requires **Python 3.11+**.

```bash
# Core engine: pydantic, PyYAML, click, rich
pip install -e .

# Optional video replay pack: numpy, opencv-headless, tqdm
pip install -e ".[repro]"

# Development tools
pip install -e ".[dev]"
```

The `nexus` command is installed as a console script. `python -m nexus` works
too.

## Quickstart

Run the core-only example:

```bash
# In this repository:
nexus run quickstart -w runs/quickstart

# In a fresh directory:
nexus init .
nexus run hello -w runs/hello
```

A run prints a step table and writes outputs relative to `-w/--workdir`:

```
quickstart  success  6f2d0b7a1c3e  21ms
Step    Node           Status   Time  Attempts
seed    io.write_json  success   2ms         1
load    io.read_json   success   0ms         1
count   core.python    success   0ms         1
check   core.assert    success   0ms         1
report  io.write_json  success   2ms         1
Outputs
  report = ".../runs/quickstart/data/report.json"
  count = 3
```

The flow itself is deliberately small: write JSON, read it back, derive a value
with Python, assert, write a report. See
[`flows/quickstart.yaml`](flows/quickstart.yaml).

```yaml
version: "2.0"
name: quickstart

vars:
  dataset_path: "data/people.json"
  report_path: "data/report.json"

steps:
  - id: seed
    use: io.write_json
    with:
      path: "${vars.dataset_path}"
      data:
        - {name: Alice, score: 91}
        - {name: Bob, score: 78}
        - {name: Carol, score: 85}

  - id: load
    needs: [seed]
    use: io.read_json
    with:
      path: "${vars.dataset_path}"

  - id: count
    needs: [load]
    use: core.python
    with:
      target: builtins.len
      args: ["${steps.load.data}"]

  - id: check
    needs: [count]
    use: core.assert
    with:
      condition: "${steps.count.result >= 3}"
      message: "expected at least three records"

  - id: report
    needs: [check, load]
    use: io.write_json
    with:
      path: "${vars.report_path}"
      data:
        rows: "${steps.load.data}"
        count: "${steps.count.result}"
        source: "${vars.dataset_path}"

outputs:
  report: "${steps.report.path}"
  count: "${steps.count.result}"
```

More examples:

| Flow | Demonstrates |
| --- | --- |
| [`flows/quickstart.yaml`](flows/quickstart.yaml) | core-only data flow: IO, `core.python`, assert, outputs |
| [`flows/features/dag.yaml`](flows/features/dag.yaml) | parallel roots and a join |
| [`flows/features/foreach.yaml`](flows/features/foreach.yaml) | `foreach`, concurrency, `when` |
| [`flows/features/retry.yaml`](flows/features/retry.yaml) | retry policy |
| [`flows/features/subflow.yaml`](flows/features/subflow.yaml) | `flow.call` composition |
| [`flows/features/on_error.yaml`](flows/features/on_error.yaml) | `on_error: continue` |
| [`flows/repro/repro_datagen.yaml`](flows/repro/repro_datagen.yaml) | synthetic video + time-series data |
| [`flows/repro/repro.yaml`](flows/repro/repro.yaml) | typed sensor overlays + video composition |

```bash
nexus run features/dag -w runs/dag
nexus run features/foreach -w runs/foreach
nexus run features/retry -w runs/retry
nexus run features/subflow -w runs/subflow
nexus run features/on_error -w runs/on-error
```

## Core concepts

| Concept | Meaning |
| --- | --- |
| **Node** | A registered Python callable with a typed input model. Example: `core.python`, `io.write_csv`. |
| **Flow** | A YAML document declaring variables, execution policy, steps and outputs. |
| **Step** | One node invocation: `id`, `use`, `with`, optional `needs` / `when` / `foreach` / `retry` / `timeout_s`. |
| **Scope** | The expression context: `vars`, `steps`, `env`, `config`, `settings`, `run`, `inputs`, plus foreach `item` / `index`. |
| **Run** | One execution with a workdir, run id, step results and flow outputs. |
| **Node pack** | A Python module that registers nodes; loaded via `node_modules` or the `nexus.nodes` entry point. |

### Execution model

1. Load and validate the flow (`FlowSpec`).
2. Build the DAG: explicit `needs` plus implicit edges from `steps.<id>` references.
3. Resolve `vars`, `inputs` and `config` against `env`, `settings` and `run`.
4. Schedule steps whose dependencies are complete.
   - `strategy: sequential` (default) also adds declaration-order edges and runs one step at a time.
   - `strategy: dag` runs every ready step, up to `max_workers`.
5. Each step resolves its `with` mapping, validates the node input model, invokes
   the node (with retries/timeout), and stores selected outputs.
6. Resolve `outputs` and return a `RunResult`.

Data never travels through hidden mutable state. A step reads earlier results
explicitly:

```yaml
- id: load
  use: core.python
  with:
    target: "myapp.data:load"
    kwargs: {path: "input/data.csv"}

- id: transform
  needs: [load]
  use: core.python
  with:
    target: "myapp.data:clean"
    args: ["${steps.load.result}"]
```

## Flow reference

```yaml
version: "2.0"                 # required major version
name: my-flow                  # defaults to the file stem
description: "..."

vars:                          # resolved in declaration order
  threshold: 0.5
  input: "${env.DATA_DIR}/input.csv"

inputs:                        # defaults for subflow invocations
  region: eu

config:                        # application config exposed as `config`
  retries: 3

execution:
  strategy: sequential         # sequential | dag
  max_workers: 1               # 1..256
  fail_fast: true
  step_timeout_s: null

steps:
  - id: load
    use: io.read_csv
    with:
      path: "${vars.input}"

  - id: filter
    use: core.python
    needs: [load]
    when: "${vars.threshold > 0}"
    with:
      target: "myapp.logic:filter_rows"
      kwargs:
        rows: "${steps.load.rows}"
        threshold: "${vars.threshold}"
    retry:
      max_attempts: 3
      delay_s: 1.0
      backoff: 2.0
      max_delay_s: 10.0
      jitter_s: 0.2
    timeout_s: 30
    on_error: fail             # fail | continue
    outputs:                   # rename/select node outputs
      clean_rows: rows

  - id: save
    needs: [filter]
    use: io.write_json
    with:
      path: "output/clean.json"
      data: "${steps.filter.clean_rows}"

outputs:
  path: "${steps.save.path}"
  row_count: "${len(steps.filter.clean_rows)}"
```

### Step fields

| Field | Description |
| --- | --- |
| `id` | Unique identifier (`[A-Za-z_][A-Za-z0-9_]*`). |
| `use` | Registered node name. |
| `with` / `inputs` | Node input mapping; strings containing `${...}` are resolved recursively. |
| `needs` | Explicit dependencies (string or list). |
| `when` | Boolean or expression; false marks the step `skipped`. |
| `foreach` | List/expression, or `{items, as, index, concurrency}`; aggregates into `{items, count}`. |
| `outputs` | List of keys or mapping `alias: node_output_key` (dotted paths allowed). |
| `retry` | Integer `max_attempts` or a retry policy mapping. |
| `timeout_s` | Per-attempt timeout in seconds. |
| `on_error` | `fail` (default) or `continue` (record failure, keep scheduling). |
| `tags` | Free-form labels. |

### Expressions

`${...}` uses a restricted Python-like language, not `eval`:

```yaml
val: "${vars.x * 2 + 1}"
name: "hello ${inputs.name}"          # mixed strings interpolate
ok: "${steps.load.status == 'success' and len(steps.load.rows) > 0}"
merged: "${merge(vars.base, {'color': [0, 255, 0]})}"
```

Supported: names, mapping attribute access, indexing/slicing, literals, lists,
tuples, dicts, arithmetic, comparisons, boolean logic, conditional expressions,
and pure helpers (`len`, `str`, `int`, `float`, `bool`, `min`, `max`, `sum`,
`abs`, `round`, `sorted`, `list`, `dict`, `any`, `all`, `range`, `merge`,
`coalesce`, `contains`, `startswith`, `endswith`, `lower`, `upper`, `split`,
`join`).

Rejected: imports, attribute/method calls, lambdas, comprehensions, dunder
access. Treat flow files as trusted configuration; do not execute untrusted
flows.

Full specification: [docs/flow-spec.md](docs/flow-spec.md).

## CLI

```bash
nexus --version
nexus run FLOW [-w DIR] [-s key=value] [--strategy sequential|dag]
               [--max-workers N] [--no-fail-fast] [--dry-run] [--json]
nexus validate FLOW [--json]
nexus plan FLOW [--format table|mermaid|json]
nexus nodes list [--tag TAG] [--format table|json]
nexus nodes show NAME [--yaml]
nexus config show [--format yaml|json]
nexus init [DIR] [--force]
```

Global options: `--project PATH`, `--config-file FILE`, `-v/--verbose`.

`run` exits `0` on success, `1` on a failed run or invalid flow. Logs go to
stderr, so `--json` stays machine-readable.

## Built-in nodes

| Group | Nodes |
| --- | --- |
| core | `core.noop`, `core.echo`, `core.python`, `core.shell`, `core.assert`, `core.fail`, `core.sleep`, `core.log` |
| io | `io.read_text`, `io.write_text`, `io.read_json`, `io.write_json`, `io.read_yaml`, `io.write_yaml`, `io.read_jsonl`, `io.write_jsonl`, `io.read_csv`, `io.write_csv`, `io.list_dir`, `io.ensure_dir`, `io.exists` |
| composition | `flow.call` |
| repro (optional) | `repro.video.split`, `repro.video.compose`, `repro.video.blank_frames`, `repro.render.frames`, `repro.datagen.video`, `repro.datagen.timeline`, `repro.timeline.from_range`, `repro.datagen.speed`, `repro.datagen.adb` |

```bash
nexus nodes show core.python
nexus nodes show io.write_csv --yaml
```

## Writing a node

```python
from typing import Any

from pydantic import Field

from nexus import NodeContext, NodeInput, node


class GreetInput(NodeInput):
    name: str = Field(default="world", description="Who to greet.")
    excited: bool = Field(default=False)


@node(
    "myapp.greet",
    inputs=GreetInput,
    tags=["myapp"],
    description="Build a greeting string.",
)
def greet(ctx: NodeContext, inputs: GreetInput) -> dict[str, Any]:
    suffix = "!" if inputs.excited else "."
    # Relative paths resolve against the run workdir.
    target = ctx.path("greeting.txt")
    target.write_text(f"hello {inputs.name}{suffix}", encoding="utf-8")
    return {"message": f"hello {inputs.name}{suffix}", "path": str(target)}
```

Register the module so the engine imports it:

```yaml
# config/nexus.yaml
node_modules:
  - "myapp.nodes"
```

or expose it from a package:

```toml
[project.entry-points."nexus.nodes"]
myapp = "myapp.nodes"
```

Node functions may be synchronous or `async def`. The call signature is always
`(ctx, inputs)`; `inputs` is validated from the `with` mapping before the node
runs.

## Configuration

Engine settings are layered, lowest to highest:

1. `EngineSettings` defaults
2. `config/nexus.yaml`
3. `config/nexus.local.yaml` (git-ignored)
4. `--config-file` / `NEXUS_CONFIG`
5. `NEXUS__*` environment variables (`__` nests keys)
6. CLI/programmatic overrides

Example:

```yaml
version: 2
flow_paths: ["flows"]
node_modules: ["myapp.nodes"]
load_entry_points: true
execution:
  strategy: sequential
  max_workers: 1
  fail_fast: true
logging:
  level: INFO
  rich: true
```

```bash
NEXUS__EXECUTION__MAX_WORKERS=4 nexus run quickstart -w runs/quickstart
nexus config show
```

Execution settings precedence inside a run is
**engine settings < explicit flow `execution` fields < CLI flags**.

## Optional packs

### Repro: video data replay

`nexus.contrib.repro` is an optional pack for aligning time-series sensor data
to video frames, rendering overlays and composing the result back into a video.
It also generates reproducible synthetic video and sensor data for testing.

Highlights:

- JSONL sensor streams are indexed once; record bodies are read on demand.
- `forward` / `backward` / `nearest` matching with explicit offset and tolerance.
- Typed renderers (`frame_info`, `speed`, `target`) receive role-based sensor
  matches through `RenderContext`.
- Camera calibration must match the frame resolution; mismatches fail with a
  clear `CameraError` rather than silently distorting boxes.
- Rendering is atomic (`overwrite`) and can run with ordered concurrency.
- The pack has its own dependencies and is only loaded when installed or
  configured.

```bash
pip install -e ".[repro]"
nexus run repro/repro_datagen -w runs/repro-data \
  -s start_time="2025-10-27 08:30:00" \
  -s end_time="2025-10-27 08:30:02" \
  -s fps=5 -s width=320 -s height=240
nexus run repro/repro -w runs/repro-data \
  -s start_time="2025-10-27 08:30:00" \
  -s end_time="2025-10-27 08:30:02" \
  -s camera=flows/repro/camera_320x240.json
```

See [the repro pack README](src/nexus/contrib/repro/README.md) and
[the repro design](docs/repro-design.md).

## Project layout

```text
nexus/
├── config/                 # nexus.yaml, local overrides, logging
├── flows/                  # runnable example flows
│   ├── quickstart.yaml
│   ├── features/           # dag, foreach, retry, subflow, on_error
│   └── repro/              # optional video replay examples
├── src/nexus/
│   ├── core/               # config, models, expressions, graph, engine
│   ├── nodes/              # general-purpose built-in nodes
│   ├── contrib/repro/      # optional video replay pack
│   ├── cli/                # click/rich CLI
│   └── main.py             # programmatic helpers
├── tests/
├── docs/
└── pyproject.toml
```

Examples are flows, not importable packages. General-purpose operations belong
in `src/nexus/nodes/`; domain logic belongs in a separate package loaded through
`node_modules` or a `nexus.nodes` entry point. See
[docs/best-practices.md](docs/best-practices.md).

## Programmatic API

```python
from nexus import Engine, load_settings

settings = load_settings(".")
engine = Engine(settings=settings)
result = engine.run("flows/quickstart.yaml", workdir="runs/api")
print(result.status, result.outputs)

if not result.ok:
    for step in result.steps.values():
        if step.error:
            print(step.id, step.error)
```

You can also build a `FlowSpec` in memory, pass `variables`, `inputs`,
`execution` overrides, or attach an `event_listener` for structured events.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[repro,dev]"

pytest -q
ruff check src tests
mypy src/nexus
```

The repro integration tests are skipped automatically when `cv2`, `numpy`,
`tqdm` or `nexus[repro]` are not installed.

## Documentation

- [Changelog](CHANGELOG.md)
- [Architecture](docs/architecture.md)
- [Flow specification](docs/flow-spec.md)
- [Best practices](docs/best-practices.md)
- [Repro design](docs/repro-design.md)
- [Repro pack](src/nexus/contrib/repro/README.md)

## License

MIT
