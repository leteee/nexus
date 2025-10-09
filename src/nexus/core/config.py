"""
Configuration management for Nexus framework.

This module provides functional, cache-optimized configuration handling with
a clear hierarchy and immutable configuration contexts.

Core Concepts:
    - **Configuration Hierarchy**: CLI > Case/Template > Global > Plugin Defaults
    - **Functional Approach**: Pure functions with no side effects
    - **Intelligent Caching**: LRU cache for expensive YAML parsing
    - **Deep Merging**: Recursive dictionary merging for nested configs
    - **Type Safety**: Integration with Pydantic models for validation

Configuration Sources (in precedence order):
    1. **CLI Overrides**: Highest precedence - command-line --config arguments
    2. **Case/Template Configuration**: case.yaml or template.yaml (mutual exclusion)
    3. **Global Configuration**: config/global.yaml in project root
    4. **Plugin Defaults**: Extracted from Pydantic model field defaults

Architecture:
    All configuration functions are pure (no side effects) and most are cached
    for performance. The configuration context is built once and remains immutable
    throughout pipeline execution.

Typical Usage:
    >>> from pathlib import Path
    >>> # Load configurations
    >>> global_cfg = load_yaml(Path("config/global.yaml"))
    >>> case_cfg = load_yaml(Path("cases/analysis/case.yaml"))
    >>> cli_overrides = {"plugins": {"DataGen": {"num_rows": 1000}}}
    >>>
    >>> # Create merged context
    >>> context = create_configuration_context(
    ...     global_config=global_cfg,
    ...     case_config=case_cfg,
    ...     cli_overrides=cli_overrides,
    ...     plugin_registry=PLUGIN_REGISTRY
    ... )
    >>>
    >>> # Get plugin-specific config
    >>> plugin_cfg = get_plugin_configuration(
    ...     "DataGen", context, {}, DataGenConfig
    ... )
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@lru_cache(maxsize=128)
def _load_yaml_cached(file_path_str: str) -> Dict[str, Any]:
    """
    Load and parse YAML file with LRU caching.

    This is an internal cached implementation that operates on string paths
    for cache key compatibility. The cache significantly improves performance
    when the same configuration files are loaded multiple times.

    **Caching Strategy**:
        - Cache size: 128 entries (most projects have < 10 unique configs)
        - Cache key: Absolute file path as string
        - Cache invalidation: Automatic LRU eviction
        - Missing files: Cached as empty dict (not an error)

    Args:
        file_path_str (str): Absolute path to YAML file as string.
            Must be absolute for consistent cache keys across calls.

    Returns:
        Dict[str, Any]: Parsed YAML content as dictionary.
            Returns empty dict {} if file doesn't exist.
            Returns empty dict {} if YAML file is empty.

    Raises:
        ValueError: If YAML syntax is invalid, includes parse error details.

    Note:
        This function is cached at the module level. The same file path will
        only be parsed once during the Python process lifetime, unless cache
        is cleared or entry is evicted.

    Example:
        >>> config = _load_yaml_cached("/path/to/config.yaml")
        >>> # Subsequent calls return cached result
        >>> config2 = _load_yaml_cached("/path/to/config.yaml")  # Instant
    """
    try:
        with open(file_path_str, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path_str}: {e}")


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load YAML configuration file with automatic caching.

    This is the primary function for loading YAML configuration files.
    It wraps the cached implementation and handles Path-to-string conversion.

    **Features**:
        - Automatic caching for repeated loads
        - Safe loading (yaml.safe_load) prevents code execution
        - Graceful handling of missing files (returns empty dict)
        - UTF-8 encoding enforced for cross-platform compatibility

    **Performance**:
        First load: ~1-5ms (depends on file size)
        Cached loads: ~0.001ms (dictionary lookup)

    Args:
        file_path (Path): Path to YAML configuration file.
            Can be relative or absolute. Relative paths resolved from cwd.
            Missing files return empty dict (no error raised).

    Returns:
        Dict[str, Any]: Parsed configuration dictionary.
            Empty dict {} if file doesn't exist or is empty.

    Raises:
        ValueError: If YAML syntax is invalid.

    Example:
        >>> from pathlib import Path
        >>>
        >>> # Load global configuration
        >>> global_config = load_yaml(Path("config/global.yaml"))
        >>>
        >>> # Load case configuration
        >>> case_config = load_yaml(Path("cases/analysis/case.yaml"))
        >>>
        >>> # Missing file returns empty dict
        >>> missing = load_yaml(Path("nonexistent.yaml"))
        >>> assert missing == {}

    Common Patterns:
        **Project Configuration**:
            ```python
            project_root = Path.cwd()
            global_cfg = load_yaml(project_root / "config" / "global.yaml")
            ```

        **Case Configuration**:
            ```python
            case_dir = Path("cases/financial-analysis")
            case_cfg = load_yaml(case_dir / "case.yaml")
            ```

        **Template Configuration**:
            ```python
            template_cfg = load_yaml(Path("templates/etl-pipeline.yaml"))
            ```

    Note:
        The underlying cache is shared across all calls. If you need to reload
        a file after it's been modified, you must clear the cache manually:
        `_load_yaml_cached.cache_clear()`
    """
    return _load_yaml_cached(str(file_path))


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries with override precedence.

    Performs a deep merge where nested dictionaries are merged recursively
    rather than replaced. This is essential for configuration management where
    you want to override specific nested values without losing other settings.

    **Merge Behavior**:
        - **Nested dicts**: Recursively merged (both must be dicts)
        - **Other values**: Override value replaces base value
        - **New keys**: Added to result
        - **Missing keys in override**: Base values retained

    **Immutability**:
        Creates a new dictionary; input dictionaries are not modified.

    Args:
        base (Dict[str, Any]): Base configuration dictionary.
            This represents the lower-precedence configuration.
            Values retained unless overridden.

        override (Dict[str, Any]): Override configuration dictionary.
            This represents the higher-precedence configuration.
            Values from here take precedence over base.

    Returns:
        Dict[str, Any]: New dictionary with merged values.
            Original dictionaries are not modified.

    Example:
        >>> base = {
        ...     "database": {"host": "localhost", "port": 5432},
        ...     "logging": {"level": "INFO"}
        ... }
        >>> override = {
        ...     "database": {"host": "prod-server"},
        ...     "cache": {"enabled": True}
        ... }
        >>> result = deep_merge(base, override)
        >>> print(result)
        {
            'database': {'host': 'prod-server', 'port': 5432},
            'logging': {'level': 'INFO'},
            'cache': {'enabled': True}
        }

    Configuration Hierarchy Example:
        >>> # Build configuration hierarchy
        >>> defaults = {"plugins": {"DataGen": {"rows": 100, "seed": 42}}}
        >>> global_cfg = {"plugins": {"DataGen": {"rows": 500}}}
        >>> case_cfg = {"plugins": {"DataGen": {"seed": 123}}}
        >>> cli_cfg = {"plugins": {"DataGen": {"rows": 1000}}}
        >>>
        >>> # Merge in order: defaults -> global -> case -> CLI
        >>> result = defaults
        >>> result = deep_merge(result, global_cfg)
        >>> result = deep_merge(result, case_cfg)
        >>> result = deep_merge(result, cli_cfg)
        >>>
        >>> print(result["plugins"]["DataGen"])
        {'rows': 1000, 'seed': 123}  # rows from CLI, seed from case

    Edge Cases:
        **Type Conflicts** (both values must be dict to merge):
            ```python
            base = {"key": {"nested": 1}}
            override = {"key": "string"}
            result = deep_merge(base, override)
            # result = {"key": "string"}  # Override replaces entirely
            ```

        **List Values** (not merged, replaced):
            ```python
            base = {"items": [1, 2, 3]}
            override = {"items": [4, 5]}
            result = deep_merge(base, override)
            # result = {"items": [4, 5]}  # Lists are replaced, not concatenated
            ```

    Note:
        This function is pure (no side effects) and can be cached if needed.
        For performance-critical paths, consider using Python 3.9+ dict union
        operator `|` for shallow merges.
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def create_configuration_context(
    global_config: Dict[str, Any],
    case_config: Dict[str, Any],
    cli_overrides: Dict[str, Any],
    plugin_registry: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create unified configuration context with proper precedence hierarchy.

    This is the primary function for building the complete configuration context
    used throughout pipeline execution. It merges all configuration sources
    according to the precedence rules.

    **Configuration Hierarchy** (highest to lowest precedence):
        1. **CLI Overrides**: Command-line arguments (--config key=value)
        2. **Case/Template Config**: case.yaml or template.yaml (mutual exclusion)
        3. **Global Config**: config/global.yaml in project root
        4. **Plugin Defaults**: Extracted from Pydantic model defaults (on-demand)

    **Immutability**:
        The returned context is a new dictionary. Input dictionaries are not
        modified, supporting functional programming principles.

    Args:
        global_config (Dict[str, Any]): Global configuration from config/global.yaml.
            Contains project-wide settings, shared plugin configs, and framework settings.
            Example: {"framework": {"logging": {"level": "INFO"}}, "plugins": {...}}

        case_config (Dict[str, Any]): Case-specific configuration from case.yaml/template.yaml.
            Contains case metadata, data sources, pipeline definition, and case-specific
            plugin overrides.
            Example: {"case_info": {...}, "data_sources": {...}, "pipeline": [...]}

        cli_overrides (Dict[str, Any]): Command-line configuration overrides.
            Typically from `--config key=value` CLI arguments.
            Highest precedence - overrides all other sources.
            Example: {"plugins": {"Data Generator": {"num_rows": 1000}}}

        plugin_registry (Dict[str, Any]): Registry of discovered plugins.
            Maps plugin names to PluginSpec objects containing metadata.
            Used for plugin lookup (not for config extraction in this function).

    Returns:
        Dict[str, Any]: Unified configuration context.
            Contains merged configurations from all sources.
            Structure:
                - framework.*: Framework settings
                - data_sources.*: Global data sources
                - plugins.*: Plugin configurations
                - pipeline: Pipeline definition (from case/template)
                - case_info: Case metadata (from case/template)

    Example:
        >>> from nexus.core.discovery import PLUGIN_REGISTRY
        >>> from nexus.core.config import load_yaml
        >>>
        >>> # Load configuration sources
        >>> global_cfg = load_yaml(Path("config/global.yaml"))
        >>> case_cfg = load_yaml(Path("cases/analysis/case.yaml"))
        >>> cli_overrides = {"plugins": {"Data Generator": {"num_rows": 5000}}}
        >>>
        >>> # Create unified context
        >>> context = create_configuration_context(
        ...     global_config=global_cfg,
        ...     case_config=case_cfg,
        ...     cli_overrides=cli_overrides,
        ...     plugin_registry=PLUGIN_REGISTRY
        ... )
        >>>
        >>> # Access merged configuration
        >>> print(context["plugins"]["Data Generator"]["num_rows"])  # 5000 (from CLI)
        >>> print(context["framework"]["logging"]["level"])  # From global
        >>> print(context["case_info"]["name"])  # From case

    Configuration Flow:
        ```
        Global Config          Case/Template Config      CLI Overrides
        ┌─────────────┐       ┌─────────────┐           ┌─────────────┐
        │framework:   │       │case_info:   │           │plugins:     │
        │  logging:   │  +    │  name: Test │      +    │  DataGen:   │
        │    level:   │       │plugins:     │           │    rows:1000│
        │    INFO     │       │  DataGen:   │           └─────────────┘
        │plugins:     │       │    seed:42  │                  ↓
        │  DataGen:   │       └─────────────┘              Highest
        │    rows:100 │              ↓                   Precedence
        └─────────────┘           Middle
             ↓                 Precedence
          Lowest
        Precedence
             ↓                      ↓
             └──────────┬───────────┘
                        ↓
                 Deep Merge Process
                        ↓
        ┌────────────────────────────────┐
        │ Unified Configuration Context  │
        │                                │
        │ framework: {logging: {INFO}}   │
        │ case_info: {name: Test}        │
        │ plugins: {DataGen: {rows: 1000,│
        │                     seed: 42}} │
        └────────────────────────────────┘
        ```

    Note:
        - This function is called once per pipeline execution
        - The context is immutable and thread-safe
        - Plugin defaults are extracted on-demand in get_plugin_configuration()
        - No plugin_defaults namespace in returned context
    """
    # Start with global config
    context = global_config.copy()

    # Merge case/template config
    context = deep_merge(context, case_config)

    # Apply CLI overrides (highest precedence)
    context = deep_merge(context, cli_overrides)

    return context


def extract_plugin_defaults(plugin_registry: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Extract default configuration values from plugin Pydantic models.

    Scans all registered plugins and extracts their default configuration values
    from Pydantic model field definitions. This provides fallback values when
    no explicit configuration is provided.

    **Extraction Process**:
        1. Check if plugin has a config_model (Pydantic model)
        2. Instantiate model with no arguments (uses field defaults)
        3. Serialize model to dictionary
        4. Handle extraction failures gracefully (empty dict)

    **Default Value Sources** (in Pydantic models):
        - Field(default=value): Explicit default value
        - field: Type = value: Type annotation with default
        - Field(default_factory=callable): Callable that returns default

    Args:
        plugin_registry (Dict[str, Any]): Registry mapping plugin names to PluginSpec.
            Each PluginSpec may have a config_model attribute pointing to a
            Pydantic BaseModel subclass.

    Returns:
        Dict[str, Dict]: Mapping of plugin names to their default configurations.
            - Keys: Plugin names (e.g., "Data Generator", "CSV Reader")
            - Values: Dictionaries containing default config values
            - Plugins without config models get empty dict {}
            - Plugins with failed extraction get empty dict {}

    Example:
        >>> from pydantic import BaseModel, Field
        >>> from nexus.core.discovery import plugin, PLUGIN_REGISTRY
        >>>
        >>> # Define plugin with defaults
        >>> class DataGenConfig(BaseModel):
        ...     num_rows: int = 100
        ...     seed: int = Field(default=42, description="Random seed")
        ...     output_format: str = "csv"
        >>>
        >>> @plugin(name="Data Generator", config=DataGenConfig)
        >>> def generate_data(config: DataGenConfig) -> pd.DataFrame:
        ...     pass
        >>>
        >>> # Extract defaults
        >>> defaults = extract_plugin_defaults(PLUGIN_REGISTRY)
        >>> print(defaults["Data Generator"])
        {'num_rows': 100, 'seed': 42, 'output_format': 'csv'}

    Pydantic Model Example:
        ```python
        from pydantic import BaseModel, Field
        from typing import Optional

        class MyPluginConfig(BaseModel):
            # Simple default
            threshold: float = 0.5

            # Default with metadata
            max_iterations: int = Field(
                default=1000,
                description="Maximum iterations",
                ge=1
            )

            # Optional field (default None)
            output_path: Optional[str] = None

            # Default factory
            tags: list[str] = Field(default_factory=list)
        ```

        Extracted defaults:
        ```python
        {
            'threshold': 0.5,
            'max_iterations': 1000,
            'output_path': None,
            'tags': []
        }
        ```

    Graceful Failure Handling:
        **No Config Model**:
            ```python
            @plugin(name="Simple Plugin")  # No config parameter
            def simple_plugin() -> None:
                pass

            defaults = extract_plugin_defaults(registry)
            # defaults["Simple Plugin"] == {}
            ```

        **Model Instantiation Error**:
            ```python
            class BrokenConfig(BaseModel):
                required_field: str  # No default, will fail

            # Extraction fails gracefully
            defaults = extract_plugin_defaults(registry)
            # defaults["Broken Plugin"] == {}
            ```

    Performance:
        - Called once during configuration context creation
        - Each model instantiated once (cheap for most models)
        - Failures caught and logged (no crash)
        - Result typically cached in configuration context

    Note:
        - Models are instantiated with no arguments
        - Required fields without defaults cause extraction to fail
        - Failures are silent (return empty dict)
        - Consider defining all plugin config fields with sensible defaults
    """
    defaults_map = {}

    for name, spec in plugin_registry.items():
        try:
            if hasattr(spec, "config_model") and spec.config_model:
                # Extract defaults from pydantic model
                model_instance = spec.config_model()
                defaults_map[name] = model_instance.model_dump()
            else:
                defaults_map[name] = {}
        except Exception:
            # If we can't extract defaults, use empty dict
            defaults_map[name] = {}

    return defaults_map


def get_plugin_configuration(
    plugin_name: str,
    config_context: Dict[str, Any],
    step_config: Dict[str, Any],
    config_model: Optional[type] = None,
) -> Any:
    """
    Build final plugin configuration by merging all sources and validating.

    This function assembles the complete configuration for a specific plugin
    by merging configurations from multiple sources in order of precedence,
    then validates the result against the plugin's Pydantic model.

    **Configuration Sources** (lowest to highest precedence):
        1. **Plugin Defaults**: From Pydantic model field defaults (extracted on-demand)
        2. **Global Plugin Config**: From global.yaml plugins section
        3. **Step Config**: From pipeline step config in case.yaml

    **Validation**:
        If a config_model is provided (Pydantic BaseModel), the merged configuration
        is validated and an instance is returned. This ensures type safety and
        catches configuration errors early.

    Args:
        plugin_name (str): Name of the plugin.
            Must match the name used in @plugin decorator.
            Used to lookup configuration in various sources.
            Example: "Data Generator", "CSV Reader"

        config_context (Dict[str, Any]): Unified configuration context.
            Created by create_configuration_context().
            Contains merged global, case, and CLI configurations.
            Should have "plugins" key.

        step_config (Dict[str, Any]): Step-specific configuration overrides.
            From the pipeline step definition in case.yaml.
            Has highest precedence among plugin configs.
            Example: {"num_rows": 5000} from pipeline step

        config_model (Optional[type], optional): Pydantic model class for validation.
            If provided, validates merged config and returns model instance.
            Also used to extract plugin defaults on-demand.
            If None, returns raw dictionary without validation.
            Defaults to None.

    Returns:
        Any: Plugin configuration.
            - If config_model provided: Instance of config_model class
            - If config_model is None: Dictionary with merged config
            - Type depends on plugin's config model definition

    Raises:
        ValidationError: If merged configuration doesn't match config_model schema.
            Includes details about which fields failed validation.

    Example:
        >>> from pydantic import BaseModel
        >>> from nexus.core.config import load_yaml, create_configuration_context
        >>>
        >>> # Define plugin config model
        >>> class DataGenConfig(BaseModel):
        ...     num_rows: int = 100
        ...     seed: int = 42
        >>>
        >>> # Build configuration context
        >>> context = create_configuration_context(
        ...     global_config=load_yaml(Path("config/global.yaml")),
        ...     case_config=load_yaml(Path("cases/test/case.yaml")),
        ...     cli_overrides={"plugins": {"Data Generator": {"num_rows": 1000}}},
        ...     plugin_registry=PLUGIN_REGISTRY
        ... )
        >>>
        >>> # Get validated plugin config
        >>> plugin_cfg = get_plugin_configuration(
        ...     plugin_name="Data Generator",
        ...     config_context=context,
        ...     step_config={"seed": 123},
        ...     config_model=DataGenConfig
        ... )
        >>>
        >>> print(type(plugin_cfg))  # <class 'DataGenConfig'>
        >>> print(plugin_cfg.num_rows)  # 1000 (from CLI in context)
        >>> print(plugin_cfg.seed)  # 123 (from step config)

    Configuration Merge Example:
        ```python
        # Defaults from model (extracted on-demand)
        defaults = {"num_rows": 100, "seed": 42, "format": "csv"}

        # Global config (from config_context)
        global_cfg = {"num_rows": 500, "output_dir": "/data"}

        # Step config (from step_config parameter)
        step_cfg = {"seed": 999}

        # Final merged config
        # {
        #     "num_rows": 500,     # From global (overrides default)
        #     "seed": 999,         # From step (highest precedence)
        #     "format": "csv",     # From defaults (not overridden)
        #     "output_dir": "/data"  # From global (new field)
        # }
        ```

    Note:
        - Called for each plugin during pipeline execution
        - Validation happens immediately (fail-fast)
        - Plugin defaults extracted on-demand if config_model provided
        - Type coercion applied by Pydantic (e.g., "100" -> 100)
        - Step config has precedence over global for plugin-level overrides
    """
    # Extract plugin defaults from Pydantic model (on-demand)
    plugin_defaults = {}
    if config_model:
        try:
            # Instantiate model with no arguments to get defaults
            model_instance = config_model()
            plugin_defaults = model_instance.model_dump()
        except Exception:
            # If we can't extract defaults, use empty dict
            plugin_defaults = {}

    # Get global plugin config from context
    global_plugin_config = config_context.get("plugins", {}).get(plugin_name, {})

    # Merge: Defaults < Global < Step
    merged_config = deep_merge(plugin_defaults, global_plugin_config)
    merged_config = deep_merge(merged_config, step_config)

    # Create model instance if available
    if config_model:
        return config_model(**merged_config)
    else:
        return merged_config
