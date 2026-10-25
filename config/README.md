# Configuration

Nexus 2.0 uses two kinds of configuration:

1. **Engine settings** — how the engine discovers flows, loads node packs, logs
   and schedules. Stored in this directory.
2. **Flow configuration** — `vars`, `inputs` and `config` inside each flow file.

## Files

| File | Tracked | Purpose |
| --- | --- | --- |
| `nexus.yaml` | yes | Project engine defaults. |
| `nexus.local.yaml` | no (git-ignored) | Machine/user overrides. |
| `nexus.local-example.yaml` | yes | Copy to `nexus.local.yaml` to start. |
| `logging.yaml` | removed | Logging is configured by `logging.*` in `nexus.yaml`. |

## Precedence

Lowest to highest:

1. built-in `EngineSettings` defaults
2. `config/nexus.yaml`
3. `config/nexus.local.yaml`
4. `--config-file FILE` (or `NEXUS_CONFIG`)
5. `NEXUS__*` environment variables (`__` nests keys)
6. CLI/programmatic overrides

Inside a run, execution policy is merged as:

```
engine settings < explicit flow execution fields < CLI flags
```

## Example

```yaml
version: 2
flow_paths: ["flows"]
# additional node packs
node_modules:
  - "myapp.nodes"
load_entry_points: true

execution:
  strategy: sequential
  max_workers: 1
  fail_fast: true

logging:
  level: INFO
  file: "logs/nexus.log"
  rich: true
```

## Environment overrides

```bash
NEXUS__EXECUTION__MAX_WORKERS=4 \
NEXUS__EXECUTION__STRATEGY=dag \
NEXUS__LOGGING__LEVEL=DEBUG \
nexus run quickstart -w runs/quickstart
```

## Node packs

Built-in general-purpose nodes load automatically. Extra packs are loaded from:

- `node_modules` (imported at engine startup), and
- the `nexus.nodes` entry point group (for installed packages).

The `repro` pack is discovered when `nexus[repro]` is installed; without its
dependencies the entry point is skipped with a warning instead of failing the
engine. Project-specific node packs go in `node_modules` or their own entry
point.

## Inspect the merged result

```bash
nexus config show            # YAML
nexus config show --format json
nexus nodes list
```
