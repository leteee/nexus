# Flow Specification (Nexus 2.0)

Nexus 2.0 flow schema. Unknown fields are rejected, so typos fail at load
time. A full example lives in [`flows/quickstart.yaml`](../flows/quickstart.yaml).

## Top-level fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `version` | string | `"2.0"` | Must be `2` or `2.x`. |
| `name` | string | file stem | Flow name used in results and logs. |
| `description` | string | `null` | Human-readable description. |
| `vars` | mapping | `{}` | Flow variables, resolved in declaration order. |
| `inputs` | mapping | `{}` | Default inputs for subflow invocation. |
| `config` | mapping | `{}` | Application config exposed as `config` in expressions. |
| `execution` | mapping | engine defaults | Strategy, workers, failure and timeout policy. |
| `steps` | list | required | Ordered step declarations. |
| `outputs` | mapping | `{}` | Flow outputs evaluated after the run. |

### Execution

```yaml
execution:
  strategy: sequential   # sequential | dag
  max_workers: 1         # 1..256, used by dag
  fail_fast: true        # stop scheduling after a fatal failure
  step_timeout_s: null   # default per-attempt timeout
```

Precedence: engine settings < explicit flow fields < `Engine.run(execution=...)`
or CLI flags. In `sequential` mode, declaration order is enforced with implicit
edges. In `dag` mode, roots can run concurrently.

## Steps

```yaml
steps:
  - id: transform
    use: core.python
    name: optional display name
    description: optional
    needs: [load]
    with:
      target: "myapp.logic:transform"
      kwargs: {rows: "${steps.load.rows}"}
    when: "${len(steps.load.rows) > 0}"
    foreach: null
    outputs: {rows: rows}
    retry: {max_attempts: 3, delay_s: 1, backoff: 2, max_delay_s: 30, jitter_s: 0}
    timeout_s: 30
    on_error: fail          # fail | continue
    tags: [etl]
```

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Unique, identifier-safe. Used by `steps.<id>` and `needs`. |
| `use` | yes | Registered node name (`pack.node`). |
| `with` | no | Alias: `inputs`. Resolved recursively before validation. |
| `needs` | no | String or list of step ids. Expression references add edges automatically. |
| `when` | no | `true`/`false` or an expression string. False => `skipped`. |
| `foreach` | no | Literal list, expression, or `{items, as, index, concurrency}`. |
| `outputs` | no | List of keys, or mapping `alias: key` (dotted paths allowed). |
| `retry` | no | Integer max attempts or a policy mapping. |
| `timeout_s` | no | Per-attempt timeout, overrides execution default. |
| `on_error` | no | `fail` (fatal) or `continue` (record and keep going). |
| `tags` | no | Free-form labels. |

### `foreach`

```yaml
- id: process
  use: myapp.process
  foreach:
    items: "${vars.files}"        # list or mapping (mapping values are used)
    as: file                      # bind current item; default "item"
    index: i                      # bind index; default "index"
    concurrency: 4                # iterations in parallel; default 1
  with:
    path: "${file}"
    position: "${i}"
```

The step output is:

```json
{"items": [{...}, {...}], "count": 2}
```

If the step declares `outputs`, that selection is applied to each item before
aggregation. Empty input produces `{"items": [], "count": 0}`.

### `needs` and implicit edges

Nexus adds a dependency for every `steps.<id>` reference found in:

- `with` values that contain `${...}`,
- `when`,
- `foreach.items`.

So these two steps are ordered even without `needs`:

```yaml
- id: load
  use: io.read_json
  with: {path: "data.json"}
- id: use
  use: core.echo
  with: {value: "${steps.load.data}"}
```

### Failure behaviour

| Setting | Effect |
| --- | --- |
| `retry.max_attempts` | Total attempts, including the first. |
| `retry.delay_s` / `backoff` | Sleep between attempts; capped by `max_delay_s`. |
| `retry.jitter_s` | Add uniform random jitter in `[0, jitter_s]`. |
| `timeout_s` | Per-attempt limit. |
| `on_error: fail` | Step failure is fatal; `fail_fast` cancels pending steps. |
| `on_error: continue` | Step is `failed`, run status is `failed`, downstream still schedules. |

A downstream step that references an output of a skipped/failed step fails with
a resolution error. Gate it with `when` or handle it explicitly.

## Output selection

A node returning a mapping exposes every key directly:

```yaml
- id: load
  use: io.read_csv
  with: {path: "data.csv"}
# ${steps.load.rows}, ${steps.load.count}, ${steps.load.path}
```

`outputs` renames or selects:

```yaml
outputs:
  rows: data
  size: meta.count
```

With the mapping above, downstream sees `steps.load.rows` and
`steps.load.size`; other keys are hidden.

## Flow outputs

```yaml
outputs:
  path: "${steps.save.path}"
  rows: "${steps.load.rows}"
```

Values without `${...}` are literals. Output resolution happens after all steps;
an error here marks the run failed.

## Expression scope

| Name | Contents |
| --- | --- |
| `vars` | Resolved flow variables + `--set`/`variables` overrides. |
| `steps` | Completed steps: output keys, `status`, `error`, `attempts`, `duration_ms`, `outputs`. Reserved metadata names (`id`, `status`, `error`, `attempts`, `duration_ms`, `outputs`) take precedence over same-named node outputs. |
| `env` | Process environment. |
| `settings` | Resolved engine settings. |
| `config` | Flow `config` mapping. |
| `run` | `id`, `flow`, `flow_path`, `workdir`, `project_root`, `started_at`, `dry_run`, `parent_run_id`. |
| `inputs` | Resolved flow inputs (subflows). |
| foreach names | `item`/`index`, or custom `as`/`index` names. |

## Expression language

```yaml
a: "${vars.x + 1}"
b: "${steps.load.rows[0]['name']}"
c: "${'yes' if vars.flag else 'no'}"
d: "${merge(vars.base, {'color': [0, 255, 0]})}"
e: "hello ${inputs.name}"       # mixed interpolation
f: "$${literal}"                # escaped, produces ${literal}
```

Whitelisted helpers: `abs`, `all`, `any`, `bool`, `coalesce`, `contains`,
`dict`, `endswith`, `float`, `int`, `join`, `len`, `list`, `lower`, `max`,
`merge`, `min`, `range`, `round`, `set`, `sorted`, `split`, `startswith`, `str`,
`sum`, `tuple`, `upper`.

Not allowed: imports, method calls, lambdas, comprehensions, dunder attributes,
starred arguments. Use a node for complex logic.

## Subflows

```yaml
- id: child
  use: flow.call
  with:
    flow: "features/child.yaml"   # path or name under flow_paths
    workdir: null                 # default: parent workdir
    inputs: {name: "nexus"}       # merged over child FlowSpec.inputs
    vars: {extra: 1}              # child variables
    inherit_vars: false
    allow_failure: false
```

Result shape:

```yaml
steps.child.child.status        # success | failed | cancelled
steps.child.child.outputs       # child flow outputs
steps.child.child.steps         # {step_id: status}
steps.child.child.error
```

Recursion and depth are checked (`EngineSettings.max_subflow_depth`).
