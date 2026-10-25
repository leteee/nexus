# Nexus 2.0 Best Practices

This repository keeps the engine small and puts examples, reusable nodes and
optional domain logic in separate places. The goal is simple: **a flow should
read like composition, not like application code.**

## 1. Repository responsibilities

| Location | Belongs here | Does not belong here |
| --- | --- | --- |
| `src/nexus/core/` | Engine: config, models, expressions, graph, scheduler | Business logic, video/domain code |
| `src/nexus/nodes/` | General-purpose nodes (`core.*`, `io.*`, `flow.*`) | Domain-specific transforms |
| `src/nexus/contrib/<pack>/` | Optional, self-contained domain packs | Core behavior or examples |
| `flows/` | Runnable examples and project flows | Python implementation |
| `tests/` | Unit, integration and end-to-end tests | Production logic |
| `docs/` | Contracts, guides, design notes | Generated API dumps |

There is intentionally **no `contrib/basic`**. A synthetic data helper is an
example concern, not a framework concern. Examples live in `flows/`; reusable
business logic belongs in a project/domain package and is loaded through
`node_modules` or a `nexus.nodes` entry point.

## 2. Where should my code go?

### General-purpose operation

Put it in `src/nexus/nodes/` only if it is useful to almost every user (files,
JSON, shell, Python bridge, flow composition). Keep it dependency-light.

### Domain operation

Create a separate package:

```text
myapp/
├── pyproject.toml
└── src/myapp/
    ├── logic.py      # plain Python, no Nexus import required
    └── nodes.py      # @node adapters over logic.py
```

Register it:

```yaml
# config/nexus.yaml
node_modules:
  - "myapp.nodes"
```

or expose an entry point:

```toml
[project.entry-points."nexus.nodes"]
myapp = "myapp.nodes"
```

Do not add domain code to `nexus.contrib` unless it is a generally useful,
maintained pack such as `repro`.

### Example

Examples are **flows**, not importable packages. Use `flows/` and keep the
quickstart core-only:

- `flows/quickstart.yaml`: IO + `core.python` + `core.assert`
- `flows/features/`: DAG, foreach, retry, subflow, on_error
- `flows/repro/`: optional real-world domain pack

## 3. Flow conventions

1. **One responsibility per step.** A step should do one thing; compose more
   steps instead of growing a mega-node.
2. **Use stable, semantic step ids.** `load_people`, `write_report`; avoid
   `step1`, `step2`.
3. **Declare dependencies explicitly** with `needs` or a `${steps.x...}` reference.
   Do not rely on declaration order in `dag` mode.
4. **Pass data explicitly.** Return mappings from nodes and read
   `${steps.<id>...}`. Do not invent hidden shared state.
5. **Prefer `start_time` / `end_time`** for time-ranged work, not a duration.
   Duration is an internal derivation.
6. **Use `when` for optional work**, not a disabled copy of the whole flow.
7. **Use `foreach` for repeated work**, and set `concurrency` intentionally.
8. **Keep expressions small.** If an expression needs comments, move the logic
   into a node.
9. **Declare flow outputs.** Callers should not have to know internal step ids.
10. **Use `--workdir`** and relative paths for reproducible runs.

## 4. Node conventions

```python
class CleanInput(NodeInput):
    rows: list[dict[str, Any]]
    threshold: float = 0.5


@node("myapp.clean", inputs=CleanInput, tags=["myapp"])
def clean(ctx: NodeContext, inputs: CleanInput) -> dict[str, Any]:
    rows = clean_rows(inputs.rows, inputs.threshold)
    return {"rows": rows, "count": len(rows)}
```

Rules:

- Keep the node function thin; put pure logic in `logic.py` and test it without
  Nexus.
- Use a typed `NodeInput`; unknown fields fail at validation.
- Resolve paths explicitly with `ctx.path(...)` or `ctx.project_path(...)`.
- Return a mapping; use `outputs` in YAML to select/rename.
- Be deterministic; accept an explicit seed instead of mutating global RNGs.
- Do not keep cross-run mutable state.
- Do not import optional heavy dependencies at module import time unless the
  pack is optional. Prefer lazy imports inside the node.
- Renderers/functions used with `workers > 1` must be stateless.

## 5. Optional domain pack checklist

A pack such as `repro` should:

1. Live under its own package and be installable via an extra
   (`pip install -e ".[repro]"`).
2. Never be imported by `nexus.core`.
3. Expose only thin `@node` adapters; keep domain types independent of Nexus
   where practical.
4. Provide typed configuration and validate it before doing work.
5. Fail with clear domain errors (`CameraError`, `TimelineError`, ...).
6. Write outputs atomically or with explicit `overwrite`; never silently
   destroy user data.
7. Avoid automatic behavior that changes semantics (for example, rescaling
   camera intrinsics for a different resolution).
8. Include unit tests plus one tiny end-to-end flow that is skipped when the
   optional dependencies are missing.

## 6. Configuration and packaging

- Use `config/nexus.yaml` for project defaults; `config/nexus.local.yaml` for
  machine-specific overrides.
- Do not put secrets in tracked config; use environment variables.
- Keep `node_modules` for explicitly configured packs.
- Use entry points for installed packs.
- Keep `repro` optional; the core dependencies stay `pydantic`, `PyYAML`,
  `click`, `rich`.

## 7. Testing

| Layer | What to test |
| --- | --- |
| Pure domain logic | Fast unit tests, no Nexus engine |
| Node adapter | Input validation, path resolution, outputs |
| Flow | Tiny run in `tmp_path`, deterministic outputs |
| Optional pack | `pytest.importorskip(...)` and a tiny e2e |
| CLI | `CliRunner` for `run` / `validate` / `plan` |

Use fixed seeds and assert semantic properties (counts, ranges, file metadata)
rather than fragile whole-file hashes. For images/video, assert dimensions, fps,
frame counts and broad pixel invariants.

## 8. Anti-patterns

- Putting domain logic in `nexus.core` or `nexus.nodes`.
- Adding an example-only pack to `src/nexus/contrib`.
- Passing data through implicit `shared_state`.
- Using global `random.seed()` / `np.random.seed()`.
- Letting a renderer load files or query sensors; pass matched data in.
- Changing camera/projection semantics based on frame size without an explicit
  calibration.
- Hardcoding fps/codec/resolution in a reusable flow instead of exposing variables.
- Deleting output directories silently on every run.
- Making `duration_s` the public time interface; use `start_time` / `end_time`.

## 9. Recommended layout

```text
nexus/
├── config/                 # engine settings
├── flows/
│   ├── quickstart.yaml     # core-only, no domain packs
│   ├── features/           # control-flow examples
│   └── repro/              # optional domain example
├── src/nexus/
│   ├── core/               # engine
│   ├── nodes/              # general-purpose nodes
│   ├── contrib/repro/      # optional domain pack
│   └── cli/
├── tests/
└── docs/
```

When in doubt: **examples go in `flows`, reusable general nodes in
`src/nexus/nodes`, domain logic in its own package.**
