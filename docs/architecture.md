# Architecture Design

Nexus is built following data_replay's functional programming principles, emphasizing immutability, pure functions, and clean separation of concerns.

## Design Philosophy

### Core Principles

1. **Immutability**: All contexts and configurations are immutable to prevent accidental side effects
2. **Functional Programming**: Pure functions with no side effects, intelligent caching
3. **Type Safety**: Comprehensive type hints and runtime validation with Pydantic
4. **Dependency Injection**: Clean separation of concerns with automatic dependency resolution
5. **Plugin Architecture**: Extensible, modular design for easy expansion
6. **Configuration Hierarchy**: Clear precedence order for configuration management

### Data_Replay Inspiration

Nexus draws inspiration from data_replay's elegant approach to data processing:

- **Functional Configuration**: Pure functions for configuration management
- **Immutable Contexts**: Dataclass-based contexts prevent mutations
- **Plugin Discovery**: Automatic registration and dependency resolution
- **Type-Safe Data Flow**: Declarative data source and sink annotations

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  nexus run  │  │nexus plugin │  │ nexus list  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     Engine Layer                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              PipelineEngine                                 ││
│  │  • Pipeline orchestration                                   ││
│  │  • Plugin execution                                         ││
│  │  • Configuration resolution                                 ││
│  │  • Dependency injection                                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Core Layer                                 │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Context   │  │  DataHub    │  │   Config    │             │
│  │ (Immutable) │  │ (Data Mgmt) │  │(Functional) │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Discovery  │  │  Handlers   │  │    Types    │             │
│  │ (Plugins)   │  │ (Data I/O)  │  │ (Protocols) │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Plugin Layer                                 │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Generators  │  │ Processors  │  │ Validators  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Custom    │  │   Custom    │  │   Custom    │             │
│  │  Plugins    │  │  Plugins    │  │  Plugins    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Context System

**Design**: Immutable dataclasses preventing accidental mutations

```python
@dataclass(frozen=True)
class NexusContext:
    project_root: Path
    case_path: Path
    logger: Logger
    run_config: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PluginContext:
    nexus_context: NexusContext
    datahub: DataHub
    config: Optional[PluginConfig] = None
```

**Benefits**:
- Thread-safe operation
- Prevents accidental state mutations
- Clear data flow
- Easy to reason about

### 2. Configuration System

**Design**: Functional approach with pure functions and caching

```python
@lru_cache(maxsize=128)
def create_configuration_context(
    project_root_str: str,
    case_path_str: str,
    plugin_registry_hash: str,
    discovered_sources_hash: str,
    cli_args_hash: str,
) -> Dict[str, Any]:
    # Pure function - no side effects
    # Cached for performance
    # Returns immutable configuration
```

**Hierarchy** (highest to lowest precedence):
1. CLI arguments (`--config`)
2. Case configuration (`case.yaml`)
3. Global configuration (`global.yaml`)
4. Plugin defaults (from code)

**Benefits**:
- Predictable configuration resolution
- No side effects
- Intelligent caching
- Clear precedence order

### 3. Plugin System

**Design**: Decorator-based registration with automatic discovery

```python
@plugin(name="My Plugin", config=MyConfig)
def my_plugin(config: MyConfig, logger) -> pd.DataFrame:
    # Plugin logic here
    return result
```

**Features**:
- Automatic registration on import
- Type-safe configuration with Pydantic
- Dependency injection
- Data source/sink annotations
- Runtime validation

### 4. Data Management

**Design**: Centralized DataHub with lazy loading and protocol-based handlers

```python
class DataHub:
    def get(self, name: str) -> Any:
        # Lazy loading with caching
        # Type checking with handlers
        # Automatic path resolution

    def save(self, name: str, data: Any) -> None:
        # Protocol-based saving
        # Automatic format detection
        # Path management
```

**Handler Protocol**:
```python
@runtime_checkable
class DataHandler(Protocol):
    def load(self, path: Path) -> Any: ...
    def save(self, data: Any, path: Path) -> None: ...
    @property
    def produced_type(self) -> type: ...
```

### 5. Pipeline Engine

**Design**: Orchestrates complete pipeline lifecycle with dependency injection

```python
class PipelineEngine:
    def run_pipeline(self, config_path, cli_overrides):
        # 1. Plugin discovery
        # 2. Configuration resolution
        # 3. Data source setup
        # 4. Plugin execution with DI
        # 5. Output management
```

**Execution Flow**:
1. Discover and register plugins
2. Load and merge configurations
3. Set up data sources in DataHub
4. Execute pipeline steps in order
5. Handle outputs and save results

## Data Flow

### 1. Configuration Flow

```
CLI Args → Case Config → Global Config → Plugin Defaults
    ↓
Merged Configuration → Type Validation → Plugin Config
```

### 2. Data Flow

```
Data Sources → DataHub Registration → Plugin Execution
    ↓
Plugin Results → DataHub Storage → Data Sinks
```

### 3. Plugin Execution Flow

```
Plugin Discovery → Configuration Resolution → Data Hydration
    ↓
Dependency Injection → Plugin Execution → Result Handling
```

## Key Design Patterns

### 1. Functional Configuration

- **Pure Functions**: No side effects, deterministic output
- **Caching**: LRU cache for expensive operations
- **Immutability**: All configurations are immutable after creation

### 2. Protocol-Based Interfaces

- **DataHandler Protocol**: Type-safe data I/O operations
- **PluginConfig Base**: Common interface for all plugin configurations
- **Runtime Type Checking**: Ensures protocol compliance

### 3. Dependency Injection

- **Constructor Injection**: Dependencies provided at creation
- **Parameter Injection**: Function parameters automatically resolved
- **Context Injection**: Runtime context provided to plugins

### 4. Plugin Architecture

- **Decorator Pattern**: Clean plugin registration
- **Discovery Pattern**: Automatic plugin detection
- **Strategy Pattern**: Pluggable data processing strategies

## Type Safety

### 1. Comprehensive Type Hints

All functions and classes include complete type annotations:

```python
def merge_configurations(
    case_config: Dict[str, Any],
    global_config: Dict[str, Any],
    plugin_defaults: Dict[str, Dict],
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
```

### 2. Runtime Validation

Pydantic models provide runtime type checking:

```python
class PluginConfig(BaseModel):
    """Base configuration class with automatic validation."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
```

### 3. Protocol Checking

Runtime protocol compliance verification:

```python
@runtime_checkable
class DataHandler(Protocol):
    # Protocol definition ensures interface compliance
```

## Extensibility

### 1. Plugin Development

New plugins integrate seamlessly:

```python
@plugin(name="Custom Plugin", config=CustomConfig)
def custom_plugin(config: CustomConfig, logger) -> Any:
    # Custom logic here
    pass
```

### 2. Data Handler Extension

New data formats supported via handlers:

```python
class CustomHandler:
    @property
    def produced_type(self) -> type:
        return CustomType

    def load(self, path: Path) -> CustomType:
        # Custom loading logic

    def save(self, data: CustomType, path: Path) -> None:
        # Custom saving logic
```

### 3. Configuration Extension

New configuration layers can be added:

```python
# Custom configuration sources
custom_config = load_custom_config()
merged = merge_configurations(case, global, plugin, custom)
```

## Performance Considerations

### 1. Lazy Loading

- Data sources loaded only when needed
- Plugin discovery cached across executions
- Configuration resolution cached

### 2. Intelligent Caching

- LRU cache for expensive operations
- Hash-based cache invalidation
- Memory-efficient data storage

### 3. Minimal Dependencies

- Core framework has minimal external dependencies
- Plugins can add specific dependencies as needed
- Optional features don't impact core performance

## Error Handling

### 1. Graceful Degradation

- Missing optional data sources don't fail pipeline
- Plugin errors are isolated and logged
- Configuration errors provide clear messages

### 2. Validation

- Early validation of configurations
- Type checking at runtime
- Clear error messages with context

### 3. Logging

- Comprehensive logging throughout execution
- Different log levels for different audiences
- Structured logging for machine processing

## Testing Strategy

### 1. Unit Tests

- Pure functions are easily testable
- Immutable contexts simplify test setup
- Protocol-based mocking

### 2. Integration Tests

- Complete pipeline execution tests
- Configuration system tests
- Plugin discovery tests

### 3. Property-Based Testing

- Configuration merging properties
- Type safety invariants
- Data flow properties

## Security Considerations

### 1. Input Validation

- All external inputs validated
- Configuration schemas enforced
- Path traversal prevention

### 2. Isolation

- Plugin execution isolated
- Configuration immutability prevents tampering
- Clear security boundaries

### 3. Dependencies

- Minimal external dependencies
- Regular dependency updates
- Vulnerability scanning

This architecture provides a solid foundation for data processing workflows while maintaining the elegance and principles of functional programming inspired by data_replay.