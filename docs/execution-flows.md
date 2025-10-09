# Execution Flows

This document provides detailed execution flow diagrams to help understand how Nexus processes data pipelines.

---

## Table of Contents

- [Overview](#overview)
- [Single Plugin Execution](#single-plugin-execution)
- [Full Pipeline Execution](#full-pipeline-execution)
- [Configuration Resolution](#configuration-resolution)
- [Data Flow](#data-flow)

---

## Overview

Nexus supports two primary execution modes:

1. **Single Plugin Execution** - Run individual plugins with `nexus plugin <name>`
2. **Full Pipeline Execution** - Run complete pipelines with `nexus run --case <case>`

---

## Single Plugin Execution

### Command
```bash
nexus plugin "My Plugin" --case mycase --config key=value
```

### Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Engine
    participant Discovery
    participant Config
    participant DataHub
    participant Plugin

    User->>CLI: nexus plugin "My Plugin" --case mycase
    CLI->>Engine: run_single_plugin(plugin_name, config_overrides)

    Engine->>Discovery: discover_plugins_from_paths()
    Discovery-->>Engine: plugin_registry

    Engine->>Discovery: get_plugin(plugin_name)
    Discovery-->>Engine: plugin_func, plugin_config_class

    alt Case config exists
        Engine->>Config: load_yaml(case.yaml)
        Config-->>Engine: case_config
    else No case config
        Engine->>Engine: _auto_discover_data_sources()
        Engine-->>Engine: minimal_config
    end

    Engine->>Config: create_configuration_context(global, case, cli)
    Config->>Config: Merge configs (CLI > Case > Global > Defaults)
    Config-->>Engine: merged_config

    Engine->>DataHub: new(project_root, case_path)
    Engine->>DataHub: register_data_sources(data_sources)
    DataHub-->>Engine: datahub

    Engine->>Config: get_plugin_configuration(plugin_name)
    Config->>Config: Extract plugin-specific config
    Config->>Config: Validate with Pydantic
    Config-->>Engine: plugin_config_instance

    Engine->>Engine: _inject_dependencies(plugin_func, config, datahub)
    Engine->>Plugin: plugin_func(config=..., logger=..., **deps)
    Plugin->>DataHub: get(data_source)
    DataHub-->>Plugin: data
    Plugin->>Plugin: Process data
    Plugin-->>Engine: result

    Engine->>Engine: _handle_plugin_output(result)
    alt Has data sinks
        Engine->>DataHub: save(sink_name, result)
        DataHub-->>Engine: saved
    end

    Engine-->>CLI: execution_result
    CLI-->>User: Success message
```

### Flow Steps

1. **Plugin Discovery**
   - Scan plugin directories and modules
   - Register all plugins in PLUGIN_REGISTRY
   - Extract plugin metadata (name, config class, dependencies)

2. **Configuration Loading**
   - Check if case.yaml exists
   - If yes: Load case configuration
   - If no: Auto-discover data files in case directory, create minimal config
   - Load global.yaml for default plugin configurations

3. **Configuration Resolution**
   - Load global.yaml (provides plugin behavior defaults)
   - Load case.yaml (if exists, or use auto-discovered config)
   - Apply CLI overrides
   - Merge with hierarchy: CLI > Case > Template > Global > Plugin Defaults

4. **DataHub Setup**
   - Create DataHub instance
   - Register global data sources (if any defined in configuration)
   - Plugin I/O paths registered automatically from DataSource/DataSink annotations
   - Set up lazy loading for data files

5. **Plugin Configuration**
   - Extract plugin-specific configuration from merged config
   - Validate against plugin's PluginConfig class
   - Create typed configuration instance

6. **Dependency Injection**
   - Inspect plugin function signature
   - Resolve dependencies:
     - `config` → Plugin configuration instance
     - `logger` → Configured logger
     - `datahub` → DataHub instance
     - Data sources → Loaded from DataHub
   - Inject all dependencies as keyword arguments

7. **Plugin Execution**
   - Call plugin function with injected dependencies
   - Plugin accesses data via DataHub
   - Plugin processes data
   - Plugin returns result

8. **Output Handling**
   - Check plugin config for DataSink annotated fields
   - If yes: Save results to specified paths via DataHub
   - Log execution summary

---

## Full Pipeline Execution

### Command
```bash
nexus run --case mycase --config key=value
```

### Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Engine
    participant Discovery
    participant Config
    participant DataHub
    participant Plugin1
    participant Plugin2
    participant PluginN

    User->>CLI: nexus run --case mycase
    CLI->>Engine: run_pipeline(case_path, config_overrides)

    Engine->>Discovery: discover_plugins_from_paths()
    Discovery-->>Engine: plugin_registry

    Engine->>Config: load_yaml(case.yaml)
    Config-->>Engine: case_config

    Engine->>Config: load_yaml(global.yaml)
    Config-->>Engine: global_config

    Engine->>Config: create_configuration_context(global, case, cli)
    Config->>Config: Merge all configurations
    Config->>Config: Resolve plugin defaults
    Config-->>Engine: merged_config

    Engine->>DataHub: new(project_root, case_path)
    Engine->>DataHub: register_data_sources(data_sources)
    DataHub-->>Engine: datahub

    Engine->>Engine: Extract pipeline steps from config

    loop For each pipeline step
        Engine->>Config: get_plugin_configuration(step.plugin)
        Config-->>Engine: plugin_config

        Engine->>Discovery: get_plugin(step.plugin)
        Discovery-->>Engine: plugin_func

        Engine->>Engine: _inject_dependencies(plugin_func)

        Engine->>Plugin1: execute(config, logger, **deps)
        Plugin1->>DataHub: get(input_data)
        DataHub-->>Plugin1: data
        Plugin1->>Plugin1: process()
        Plugin1-->>Engine: result

        Engine->>Engine: _handle_plugin_output(result)
        alt Has data_sinks
            Engine->>DataHub: save(sink, result)
        end

        Note over Engine: Continue to next step
    end

    Engine->>Plugin2: execute(config, logger, **deps)
    Plugin2->>DataHub: get(previous_output)
    DataHub-->>Plugin2: data
    Plugin2->>Plugin2: process()
    Plugin2-->>Engine: result
    Engine->>DataHub: save(sink, result)

    Engine->>PluginN: execute(config, logger, **deps)
    PluginN->>DataHub: get(input)
    DataHub-->>PluginN: data
    PluginN->>PluginN: process()
    PluginN-->>Engine: final_result
    Engine->>DataHub: save(final_sink, final_result)

    Engine-->>CLI: pipeline_results
    CLI-->>User: Pipeline completed successfully
```

### Flow Steps

1. **Initialization Phase**
   - Discover all available plugins
   - Load case configuration (case.yaml)
   - Load global configuration (global.yaml)
   - Parse CLI overrides

2. **Configuration Resolution Phase**
   - Create unified configuration context
   - Merge configurations with proper precedence
   - Extract plugin defaults from registry
   - Validate configuration schema

3. **Setup Phase**
   - Initialize DataHub
   - Register all data sources
   - Parse pipeline definition
   - Validate pipeline structure

4. **Execution Phase** (For each step)
   - Extract step configuration
   - Get plugin function from registry
   - Prepare plugin-specific configuration
   - Inject dependencies (config, logger, datahub, data sources)
   - Execute plugin
   - Handle outputs and data sinks
   - Save intermediate results to DataHub

5. **Completion Phase**
   - Verify all steps completed
   - Save final outputs
   - Generate execution summary
   - Log pipeline statistics

---

## Configuration Resolution

### Sequence Diagram

```mermaid
sequenceDiagram
    participant Engine
    participant Config
    participant YAML
    participant Registry
    participant Pydantic

    Engine->>Config: create_configuration_context()

    Config->>YAML: load_yaml(global.yaml)
    YAML-->>Config: global_config

    Config->>YAML: load_yaml(case.yaml)
    YAML-->>Config: case_config

    Config->>Registry: Extract plugin defaults
    Registry-->>Config: plugin_defaults

    Config->>Config: Parse CLI overrides

    Config->>Config: deep_merge(global, plugin_defaults)
    Config->>Config: deep_merge(result, case)
    Config->>Config: deep_merge(result, cli)

    Config-->>Engine: merged_config

    Engine->>Config: get_plugin_configuration(plugin_name)
    Config->>Config: Extract plugin section
    Config->>Pydantic: Validate against PluginConfig

    alt Validation succeeds
        Pydantic-->>Config: typed_config_instance
        Config-->>Engine: plugin_config
    else Validation fails
        Pydantic-->>Config: ValidationError
        Config-->>Engine: raise ConfigurationError
    end
```

### Hierarchy (Highest to Lowest Precedence)

```
┌─────────────────────────────────────┐
│      1. CLI Arguments               │  Highest Priority
│      --config key=value             │
└─────────────────────────────────────┘
              ↓ Overrides
┌─────────────────────────────────────┐
│      2. Case Configuration          │
│      case.yaml                      │
└─────────────────────────────────────┘
              ↓ Overrides
┌─────────────────────────────────────┐
│      3. Template Configuration      │
│      templates/*.yaml               │
└─────────────────────────────────────┘
              ↓ Overrides
┌─────────────────────────────────────┐
│      4. Global Configuration        │
│      config/global.yaml             │
└─────────────────────────────────────┘
              ↓ Overrides
┌─────────────────────────────────────┐
│      5. Plugin Defaults             │  Lowest Priority
│      From PluginConfig class        │
└─────────────────────────────────────┘
```

---

## Data Flow

### Sequence Diagram

```mermaid
sequenceDiagram
    participant Config
    participant DataHub
    participant Handler
    participant FileSystem
    participant Plugin
    participant Cache

    Config->>DataHub: register_data_source(name, path, handler_type)
    DataHub->>DataHub: Store source metadata (not loaded yet)

    Plugin->>DataHub: get(data_source_name)

    alt Data in cache
        DataHub->>Cache: Check cache
        Cache-->>DataHub: cached_data
        DataHub-->>Plugin: data
    else Data not cached
        DataHub->>DataHub: Lookup source metadata
        DataHub->>Handler: get_handler(handler_type)
        Handler-->>DataHub: handler_instance

        DataHub->>DataHub: resolve_path(source_path)
        alt Glob pattern
            DataHub->>FileSystem: glob(pattern)
            FileSystem-->>DataHub: [file1, file2, ...]
            DataHub->>Handler: load_multiple(files)
        else Absolute path
            DataHub->>Handler: load(absolute_path)
        else Relative path
            DataHub->>FileSystem: resolve relative to case_path
            DataHub->>Handler: load(resolved_path)
        end

        Handler->>FileSystem: Read file
        FileSystem-->>Handler: raw_data
        Handler->>Handler: Parse and validate
        Handler-->>DataHub: typed_data

        DataHub->>Cache: Store in cache
        DataHub-->>Plugin: data
    end

    Plugin->>Plugin: Process data
    Plugin-->>Plugin: result

    alt Plugin has data_sinks
        Plugin-->>DataHub: (returns result)
        DataHub->>DataHub: save(sink_name, result)
        DataHub->>Handler: get_handler(output_type)
        Handler-->>DataHub: output_handler
        DataHub->>Handler: save(data, output_path)
        Handler->>FileSystem: Write file
    end
```

### Path Resolution Rules

1. **Glob Patterns** (`**/*.csv`)
   - Treated as glob patterns
   - Searched relative to case directory
   - Multiple files loaded and combined

2. **Absolute Paths** (`C:\data\file.csv` or `/data/file.csv`)
   - Used as-is
   - No path resolution needed

3. **Relative Paths** (`data/input.csv`)
   - Resolved relative to case directory
   - Falls back to project root if not found in case

4. **Named Sources** (`raw_data`)
   - Looked up in data_sources configuration
   - Path resolution applied based on configured path

---

## Key Concepts

### Lazy Loading
- Data files are NOT loaded during registration
- Data is loaded only when `datahub.get()` is called
- Loaded data is cached for subsequent access
- Reduces memory footprint for large pipelines

### Dependency Injection
- Plugin dependencies are automatically resolved
- Inspection of function signature determines required dependencies
- Dependencies injected as keyword arguments
- Supports: config, logger, datahub, and any registered data source

### Configuration Caching
- Configuration resolution is cached using `@lru_cache`
- Cache key includes hashes of all configuration sources
- Cache invalidates when any configuration changes
- Improves performance for repeated executions

### Immutable Contexts
- All contexts are frozen dataclasses
- Prevents accidental mutations during execution
- Enables safe concurrent execution
- Makes data flow easier to reason about

---

## Performance Characteristics

### Single Plugin Execution
- **Overhead**: Minimal (plugin discovery + config resolution)
- **Memory**: Only loads required data sources
- **Speed**: Fast for individual plugins

### Full Pipeline Execution
- **Overhead**: Moderate (full config resolution + all plugins discovered)
- **Memory**: Loads data sources as needed (lazy loading)
- **Speed**: Depends on pipeline complexity and data size

### Optimization Tips

1. **Use caching**: Configuration and data are cached automatically
2. **Lazy loading**: Don't access unnecessary data sources
3. **Selective discovery**: Use specific plugin paths for faster discovery
4. **Configuration**: Keep configurations small and focused

---

## Error Handling Flow

```mermaid
sequenceDiagram
    participant Engine
    participant Plugin
    participant DataHub
    participant Logger

    Engine->>Plugin: execute()

    alt Plugin execution error
        Plugin-->>Engine: raise PluginError
        Engine->>Logger: log error with context
        Engine-->>User: Detailed error message
    else Configuration error
        Plugin-->>Engine: raise ValidationError
        Engine->>Logger: log validation failure
        Engine-->>User: Configuration error details
    else Data loading error
        Plugin->>DataHub: get(source)
        DataHub-->>Plugin: raise DataLoadError
        Plugin-->>Engine: propagate error
        Engine->>Logger: log data error
        Engine-->>User: Data access error
    else Success
        Plugin-->>Engine: result
        Engine->>Logger: log success
        Engine-->>User: Success message
    end
```

### Error Categories

1. **Configuration Errors**
   - Invalid YAML syntax
   - Schema validation failures
   - Missing required fields
   - Type mismatches

2. **Plugin Errors**
   - Plugin not found
   - Missing dependencies
   - Execution failures
   - Invalid outputs

3. **Data Errors**
   - File not found
   - Invalid file format
   - Type mismatches
   - I/O errors

4. **System Errors**
   - Permission issues
   - Out of memory
   - Disk space issues

---

This document provides a comprehensive view of how Nexus executes plugins and pipelines. For more details on specific components, refer to the [Architecture](architecture.md) documentation.
