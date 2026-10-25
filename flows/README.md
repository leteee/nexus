# Example flows

Run any flow by path or by name (names are searched under `flow_paths`,
`flows` by default). Relative paths inside a flow resolve against `-w`.

`quickstart.yaml` uses only built-in `core`/`io` nodes. `features/` contains
control-flow examples; `repro/` is an optional domain pack. There is no
example-only `contrib/basic` package.

```bash
nexus run quickstart -w runs/quickstart

nexus run features/dag -w runs/dag
nexus run features/foreach -w runs/foreach
nexus run features/retry -w runs/retry
nexus run features/subflow -w runs/subflow
nexus run features/on_error -w runs/on-error

# Repro; requires: pip install -e ".[repro]"
# Defaults to 1920x1080 @ 30fps; the 2s range keeps the demo quick.
nexus run repro/repro_datagen -w runs/repro-data \
  -s start_time="2025-10-27 08:30:00" -s end_time="2025-10-27 08:30:02"
nexus run repro/repro -w runs/repro-data \
  -s start_time="2025-10-27 08:30:00" -s end_time="2025-10-27 08:30:02" \
  -s workers=2
```

| File | Demonstrates |
| --- | --- |
| `quickstart.yaml` | core-only flow: IO, `core.python`, assert, outputs |
| `features/dag.yaml` | parallel roots + join |
| `features/foreach.yaml` | foreach, per-item names, concurrency, when |
| `features/retry.yaml` | retry policy |
| `features/subflow.yaml` + `features/child.yaml` | `flow.call` |
| `features/on_error.yaml` | `on_error: continue` |
| `repro/repro_datagen.yaml` | synthetic video and time-series data (repro) |
| `repro/repro.yaml` | frame split, typed sensor overlays, parallel render, compose |
