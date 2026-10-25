# Changelog

## 2.0.0

Nexus 2.0 is the current engine and domain-pack contract.

### Engine

- New `FlowSpec` / `StepSpec` schema with typed node inputs.
- DAG scheduler with `sequential` and `dag` strategies, bounded parallel execution.
- `when`, `foreach`, retry, timeout, `on_error` and `flow.call` composition.
- Explicit `${...}` expressions instead of hidden shared state.
- Layered `EngineSettings`, environment overrides and flow-level `vars` / `config`.
- Structured `RunResult`, runtime events, `--json` output and `nexus plan`.
- Node registry with `node_modules` and `nexus.nodes` entry points.
- New CLI: `run`, `validate`, `plan`, `nodes`, `config`, `init`.

### Repro pack

- Optional video replay pack with indexed JSONL sensor access.
- `forward` / `backward` / `nearest` matching with offset and tolerance.
- Typed renderer registry: `frame_info`, `speed`, `target`.
- Strict camera calibration matching; no implicit intrinsic scaling.
- Deterministic datagen with instance-local RNGs.
- Atomic frame rendering, optional ordered concurrency and explicit overwrite.

### Packaging

- Requires Python 3.11+.
- Core dependencies: `pydantic`, `PyYAML`, `click`, `rich`.
- Optional `repro` extra: `numpy`, `opencv-python-headless`, `tqdm`.
- General-purpose examples live in `flows/`; domain code lives in optional packs.

### Breaking from 1.x

- The `@plugin` / `PluginContext` API, `pipeline:` YAML, `case.yaml`,
  template resolution and `@defaults.*` references are removed.
- Flows use the 2.0 schema and explicit node inputs/outputs.
