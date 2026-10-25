# Nexus 2.0 Architecture

Nexus 2.0 is a **configurable, orchestratable Python logic execution engine**.
The 2.0 release covers both the engine and the optional `repro` redesign; flows
use the 2.0 schema. The core is deliberately small: it validates a declarative flow, schedules its
steps, and mediates inputs/outputs. Domain logic lives in node packs.

## Design goals

1. **Logic in Python, composition in config.** Nodes are normal functions; flows
   are data. No code generation, no import side effects in flow files.
2. **Explicit data flow.** Steps read from `steps.<id>` through expressions.
   There is no hidden mutable `shared_state`.
3. **Typed boundaries.** Each node declares a Pydantic input model. Bad config
   fails before the node runs.
4. **Predictable scheduling.** A validated DAG, optional parallel execution,
   explicit failure policies, and deterministic declaration-order tie breaking.
5. **Optional domain packs.** The core depends only on pydantic, PyYAML, click
   and rich. Video replay is an optional extra.

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│ CLI / programmatic API                                       │
│ run · validate · plan · nodes · config · Engine.run()        │
├──────────────────────────────────────────────────────────────┤
│ Engine                                                       │
│ scope building · scheduler · retries · timeout · subflows    │
├──────────────────────────────────────────────────────────────┤
│ Flow model & graph                                           │
│ FlowSpec · StepSpec · validation · DAG · plans               │
├──────────────────────────────────────────────────────────────┤
│ Expressions & configuration                                  │
│ safe AST evaluator · ${...} · layered EngineSettings         │
├──────────────────────────────────────────────────────────────┤
│ Node registry & built-in nodes                               │
│ @node · NodeSpec · core/io/flow · optional packs             │
└──────────────────────────────────────────────────────────────┘
```

| Module | Responsibility |
| --- | --- |
| `nexus.core.config` | Layered `EngineSettings`, env overrides, flow path resolution |
| `nexus.core.models` | Pydantic contracts for flows, steps, runs and events |
| `nexus.core.expr` | Safe expression evaluator and template interpolation |
| `nexus.core.registry` | `@node` decorator, `NodeSpec`, node pack loading |
| `nexus.core.graph` | Dependency edges, cycle detection, topological levels |
| `nexus.core.loader` | YAML loading, structural + node validation |
| `nexus.core.context` | `NodeContext` (paths, scope, events, subflows) |
| `nexus.core.engine` | Scheduler and run lifecycle |
| `nexus.nodes` | General-purpose nodes |
| `nexus.contrib.repro` | Repro domain pack (optional extras) |

## Run lifecycle

1. **Load**: `load_flow_file` parses YAML into `FlowSpec`; `name` defaults to the
   file stem.
2. **Effective execution**: engine defaults, explicit flow `execution` fields and
   run/CLI overrides are merged into one `ExecutionSettings`.
3. **Validate**: `validate_flow` checks every `use` against the registry and
   builds the graph.
4. **Graph**: dependencies = explicit `needs` + implicit `steps.<id>` refs.
   Sequential mode adds declaration-order edges. Cycles and unknown refs fail.
5. **Scope**: build `env`, `settings`, `run`, `inputs`, `vars`, `config`.
   Variables resolve in declaration order against the scope built so far.
6. **Schedule**: ready steps (all dependencies complete) are submitted to a
   thread pool. Each completion updates the step table and may unblock more.
7. **Step execution**: resolve `with` recursively, validate inputs, invoke the
   node (sync or async), apply retries/timeout, select outputs.
8. **Finish**: resolve flow `outputs`, compute status, emit events, return a
   `RunResult`.

## Scheduling semantics

- A step is **ready** when every dependency has a result, regardless of that
  result's status. A skipped or failed dependency does not block scheduling by
  itself; referencing missing outputs is what fails a downstream step.
- `strategy: sequential` means one worker and declaration-order edges. It is the
  safest default for file-oriented steps.
- `strategy: dag` allows every ready step to run, bounded by `max_workers`.
- `fail_fast: true` stops scheduling new work after a fatal failure. Pending
  steps become `cancelled`; already-running steps finish and are recorded.
- `on_error: continue` marks the step failed but returns `fatal=False` to the
  scheduler, so downstream steps still run.
- A run is `failed` if any step failed, even when `on_error: continue` allowed
  the rest of the flow to complete.

### Why no hidden state?

Implicit shared state makes parallel execution undecidable and debugging hard.
Nexus instead gives each step a snapshot of completed step results. Data
dependencies are visible in the YAML and also become graph edges, so two steps
that read each other cannot run concurrently by accident.

## Expressions

Expressions are evaluated with an AST interpreter (`nexus.core.expr`), not
`eval`. The language is intentionally small: names, mapping access, indexing,
literals, arithmetic/comparison/boolean operators, conditional expressions and
a whitelist of pure functions. Attribute access is limited to mappings and
Pydantic models; dunder names and method calls are rejected.

Static analysis extracts `steps.<id>` references from `${...}` blocks and
`when`/`foreach` expressions. That is what creates implicit DAG edges and what
lets validation catch references to unknown steps.

## Node contract

```python
@node("pack.name", inputs=MyInput)
def run(ctx: NodeContext, inputs: MyInput) -> dict[str, Any]:
    ...
```

- Inputs are validated from the resolved `with` mapping.
- A mapping return value becomes the step output namespace.
- A scalar return becomes `{"result": value}`; `None` becomes `{}`.
- `outputs` can select or rename keys, including dotted paths.
- Async functions are awaited; a sync function returning an awaitable is also
  awaited.

## Failure and timeout

- Retries are per step (and per foreach iteration). Backoff is
  `delay_s * backoff**(attempt-1)`, capped by `max_delay_s`, plus optional
  jitter.
- Timeouts are per attempt. Async nodes use `asyncio.wait_for`; sync nodes use a
  single-thread future. A timed-out sync thread cannot be forcibly killed, so it
  may continue in the background after the step is marked failed. Prefer async
  nodes or subprocesses for hard cancellation.
- `StepResult` carries `error` and `error_traceback`. CLI prints the error;
  `-v` prints tracebacks.

## Subflows

`flow.call` starts a child `Engine.run` with:

- a new run id and the parent workdir (or a child workdir),
- child `inputs` merged over `FlowSpec.inputs`,
- optionally inherited parent variables,
- a recursion/depth check (`max_subflow_depth`, default 8).

The child result is exposed as
`steps.<id>.child.{status,outputs,steps,error}`. Parent variables are not
implicitly visible unless `inherit_vars: true`.

## Extension points

| Point | How |
| --- | --- |
| New node | `@node` + input model, then `node_modules` or entry point |
| New node pack | Python package with `nexus.nodes` entry point |
| Custom transport/scheduler | Wrap `Engine` or call `NodeContext.run_flow` |
| Observability | `Engine(event_listener=...)` receives `RunEvent`s |
| Programmatic embedding | `Engine.run(FlowSpec, variables=..., execution=...)` |

## Deliberate trade-offs

- **No expression power tools** (comprehensions, lambdas, imports). Security and
  predictability beat convenience; use `core.python` for complex logic.
- **Threads, not processes.** Nodes can share in-memory objects conveniently.
  CPU-bound nodes should use their own process pools or subprocesses.
- **No resume/checkpointing in 2.0.** Runs are reproducible from config, but
  there is no persisted run store yet.
- **Trusted flows.** The expression layer is sandboxed, but `core.python` and
  `core.shell` intentionally execute arbitrary code/commands. Only run trusted
  flow files.
