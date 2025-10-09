"""
Pipeline execution engine for Nexus framework.

This module provides the PipelineEngine class for orchestrating data pipeline execution
with intelligent configuration management, plugin discovery, and data flow handling.

Core Concepts:
    - **Case-Based Execution**: All data paths resolved relative to case directory
    - **Configuration Hierarchy**: CLI overrides > Case config > Global config > Plugin defaults
    - **Dependency Injection**: Automatic resolution and injection of plugin dependencies
    - **Lazy Data Loading**: Data files loaded only when accessed by plugins
    - **Auto-Discovery**: Automatic plugin and data source discovery

Execution Modes:
    1. **Full Pipeline**: Execute multi-step pipelines defined in case.yaml
    2. **Single Plugin**: Execute individual plugins with auto-discovery

Typical Usage:
    >>> from pathlib import Path
    >>> engine = PipelineEngine(
    ...     project_root=Path("/project"),
    ...     case_dir=Path("/project/cases/analysis")
    ... )
    >>>
    >>> # Run full pipeline
    >>> results = engine.run_pipeline(pipeline_config, cli_overrides)
    >>>
    >>> # Run single plugin
    >>> result = engine.run_single_plugin("Data Generator", {"num_rows": 1000})
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, get_type_hints

from .config import (
    create_configuration_context,
    get_plugin_configuration,
    load_yaml,
)
from .context import NexusContext, PluginContext
from .datahub import DataHub
from .discovery import (
    PLUGIN_REGISTRY,
    discover_handlers_from_paths,
    discover_plugins_from_directory,
    discover_plugins_from_module,
    discover_plugins_from_paths,
    get_plugin,
)
from .types import DataSink, DataSource

logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    Pipeline execution engine with automatic dependency management.

    The PipelineEngine orchestrates the complete pipeline lifecycle:
    1. **Plugin Discovery**: Automatically discovers plugins from multiple sources
    2. **Configuration Resolution**: Merges configurations with proper precedence
    3. **Data Management**: Sets up DataHub with auto-discovered data sources
    4. **Plugin Execution**: Executes plugins with dependency injection
    5. **Output Handling**: Saves results to specified data sinks

    **Key Features**:
        - Automatic plugin discovery from modules and directories
        - Intelligent configuration merging (CLI > Case > Global > Defaults)
        - Lazy loading of data sources for memory efficiency
        - Type-safe plugin configuration with Pydantic validation
        - Comprehensive logging throughout execution

    **Architecture**:
        - **Immutable Context**: Frozen dataclasses prevent state mutations
        - **Dependency Injection**: Plugin dependencies auto-resolved from signatures
        - **Path Resolution**: Smart resolution of relative, absolute, and glob paths
        - **Error Isolation**: Plugin failures don't crash entire pipeline

    Attributes:
        project_root (Path): Root directory of the Nexus project
        case_dir (Path): Directory of the current case being executed
        logger (Logger): Logger instance for execution tracking
        context (NexusContext): Immutable execution context

    Example:
        >>> from pathlib import Path
        >>> engine = PipelineEngine(
        ...     project_root=Path("/project"),
        ...     case_dir=Path("/project/cases/financial-analysis")
        ... )
        >>>
        >>> # Execute full pipeline from case.yaml
        >>> pipeline_config = load_yaml(case_dir / "case.yaml")
        >>> results = engine.run_pipeline(
        ...     pipeline_config,
        ...     config_overrides={"plugins": {"DataGenerator": {"num_rows": 5000}}}
        ... )
        >>>
        >>> # Execute single plugin with auto-discovery
        >>> result = engine.run_single_plugin(
        ...     "Data Validator",
        ...     config_overrides={"threshold": 0.95}
        ... )

    Note:
        The engine automatically discovers plugins and handlers during initialization.
        This may take a few seconds on first run, but subsequent executions benefit
        from Python's import caching.
    """

    def __init__(self, project_root: Path, case_dir: Path):
        """
        Initialize PipelineEngine with project and case context.

        Sets up the execution environment by:
        1. Storing project and case directory references
        2. Discovering all available plugins and handlers
        3. Creating immutable execution context

        Args:
            project_root (Path): Absolute path to project root directory.
                Must contain config/, src/nexus/plugins/, and templates/ subdirectories.

            case_dir (Path): Absolute path to case directory.
                This is where data files are stored and resolved from.
                Will be created if it doesn't exist during execution.

        Example:
            >>> from pathlib import Path
            >>> engine = PipelineEngine(
            ...     project_root=Path("/home/user/myproject"),
            ...     case_dir=Path("/home/user/myproject/cases/analysis")
            ... )

        Note:
            Plugin discovery happens during initialization and may take a moment.
            The discovery process scans:
            - Built-in plugins (nexus.plugins.*)
            - Project plugins (src/nexus/plugins/)
            - Custom plugin paths from global.yaml
            - Handler modules for data I/O
        """
        self.project_root = project_root
        self.case_dir = case_dir
        self.logger = logger

        # Initialize plugin discovery
        self._discover_plugins()

        # Create immutable context
        self.context = NexusContext(
            project_root=project_root,
            case_path=case_dir,
            logger=self.logger,
        )

    def _discover_plugins(self):
        """
        Discover and register plugins from multiple sources.

        Scans the following locations in order:
        1. **Built-in Plugins**: nexus.plugins.generators, processors, validators
        2. **Project Plugins**: {project_root}/src/nexus/plugins/
        3. **Custom Paths**: Additional paths specified in global.yaml
        4. **Data Handlers**: Handler classes for CSV, JSON, Parquet, etc.

        The discovered plugins are registered in PLUGIN_REGISTRY for later lookup.

        Discovery Process:
            - Module discovery: Import and scan Python modules for @plugin decorators
            - Directory discovery: Recursively scan directories for plugin files
            - Path discovery: Scan specific paths from configuration
            - Handler discovery: Find DataHandler implementations

        Side Effects:
            - Populates global PLUGIN_REGISTRY with discovered plugins
            - Logs the total number of discovered plugins

        Example Output:
            INFO: Plugin registry contains 15 plugins

        Note:
            This method is called automatically during __init__. Discovery results
            are cached at the module level, so repeated engine initialization is fast.
        """
        # Discover from built-in plugins
        discover_plugins_from_module("nexus.plugins.generators")
        discover_plugins_from_module("nexus.plugins.processors")
        discover_plugins_from_module("nexus.plugins.validators")

        # Discover from project directories
        plugins_dir = self.project_root / "src" / "nexus" / "plugins"
        if plugins_dir.exists():
            discover_plugins_from_directory(plugins_dir)

        # Discover from global config paths
        global_config = load_yaml(self.project_root / "config" / "global.yaml")
        discovery_config = global_config.get("framework", {}).get("discovery", {})

        # Discover plugins from configured paths and modules
        plugin_config = discovery_config.get("plugins", {})
        plugin_modules = plugin_config.get("modules", [])
        plugin_paths = plugin_config.get("paths", [])

        for module_name in plugin_modules:
            discover_plugins_from_module(module_name)

        if plugin_paths:
            discover_plugins_from_paths([self.project_root / p for p in plugin_paths])

        # Discover handlers from configured paths
        handler_config = discovery_config.get("handlers", {})
        handler_paths = handler_config.get("paths", [])

        handlers_dir = self.project_root / "src" / "nexus" / "core"
        handler_scan_paths = [handlers_dir]
        if handler_paths:
            handler_scan_paths.extend([self.project_root / p for p in handler_paths])

        discover_handlers_from_paths(handler_scan_paths, self.project_root)

        self.logger.info(f"Plugin registry contains {len(PLUGIN_REGISTRY)} plugins")

    def run_pipeline(
        self,
        pipeline_config: Dict[str, Any],
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a complete multi-step pipeline.

        This is the primary method for running full data pipelines defined in case.yaml
        or template files. It orchestrates the entire execution lifecycle:

        **Execution Flow**:
            1. Load global configuration from config/global.yaml
            2. Merge configurations: CLI overrides > Pipeline config > Global config
            3. Initialize DataHub with case directory context
            4. Register all globally-defined data sources
            5. Execute each pipeline step sequentially
            6. Collect and return all step results

        **Pipeline Configuration Structure**:
            The pipeline_config should contain:
            - **case_info** (dict): Metadata about the case
            - **data_sources** (dict): Global data source definitions
            - **pipeline** (list): Sequential list of plugin execution steps

        **Step Execution**:
            Each step is executed in order, with outputs from earlier steps
            available to later steps via DataHub. Steps can:
            - Access data from any registered data source
            - Save outputs to data sinks for downstream consumption
            - Override plugin configuration at the step level

        Args:
            pipeline_config (Dict[str, Any]): Complete pipeline configuration.
                Typically loaded from case.yaml or template.yaml.
                Must contain a 'pipeline' key with list of step definitions.
                Each step must have a 'plugin' field specifying the plugin name.

            config_overrides (Optional[Dict[str, Any]], optional): CLI configuration overrides.
                Applied with highest precedence in the configuration hierarchy.
                Format: {"plugins": {"PluginName": {"param": value}}}
                Defaults to None.

        Returns:
            Dict[str, Any]: Dictionary mapping step identifiers to their results.
                Keys: "step_1_result", "step_2_result", etc.
                Values: Whatever each plugin returns (DataFrame, dict, list, etc.)

        Raises:
            ValueError: If pipeline configuration is missing or invalid:
                - No 'pipeline' key in configuration
                - Pipeline steps list is empty
                - Step missing required 'plugin' field

            FileNotFoundError: If global.yaml not found

            PluginError: If plugin execution fails

            ValidationError: If plugin configuration validation fails

        Example:
            >>> from pathlib import Path
            >>> from nexus.core.config import load_yaml
            >>>
            >>> # Load pipeline configuration
            >>> pipeline_config = load_yaml(Path("cases/analysis/case.yaml"))
            >>>
            >>> # Create engine
            >>> engine = PipelineEngine(
            ...     project_root=Path.cwd(),
            ...     case_dir=Path("cases/analysis")
            ... )
            >>>
            >>> # Execute pipeline
            >>> results = engine.run_pipeline(pipeline_config)
            >>> print(results.keys())  # dict_keys(['step_1_result', 'step_2_result', ...])
            >>>
            >>> # With CLI overrides
            >>> results = engine.run_pipeline(
            ...     pipeline_config,
            ...     config_overrides={
            ...         "plugins": {
            ...             "Data Generator": {"num_rows": 10000},
            ...             "Data Validator": {"threshold": 0.99}
            ...         }
            ...     }
            ... )

        Pipeline Configuration Example:
            ```yaml
            case_info:
              name: "Financial Analysis"
              description: "Quarterly financial data pipeline"

            data_sources:
              raw_transactions:
                path: "data/transactions.csv"
                handler: "csv"

            pipeline:
              - plugin: "Data Cleaner"
                config:
                  remove_nulls: true

              - plugin: "Feature Engineer"
                config:
                  create_ratios: true

              - plugin: "Report Generator"
                config:
                  format: "pdf"
            ```

        Note:
            - Pipeline steps execute sequentially in the order defined
            - Each step has access to all data sources registered in DataHub
            - Step results are cached in DataHub for downstream access
            - Configuration validation happens before execution
            - Execution stops on first step failure (no error recovery)
        """
        config_overrides = config_overrides or {}

        # Load global configuration
        global_config = load_yaml(self.project_root / "config" / "global.yaml")

        # Create configuration context with proper hierarchy
        config_context = create_configuration_context(
            global_config=global_config,
            case_config=pipeline_config,  # This includes the pipeline definition
            cli_overrides=config_overrides,
            plugin_registry=PLUGIN_REGISTRY,
        )

        # Initialize DataHub
        data_hub = DataHub(self.case_dir, self.logger)

        # Register global data sources (if any)
        global_data_sources = pipeline_config.get("data_sources", {})
        if global_data_sources:
            data_hub.register_global_sources(global_data_sources)

        # Execute pipeline steps
        pipeline_steps = pipeline_config.get("pipeline", [])
        if not pipeline_steps:
            raise ValueError("No pipeline steps defined in configuration")

        self.logger.info(f"Executing pipeline with {len(pipeline_steps)} steps")

        results = {}
        for i, step in enumerate(pipeline_steps, 1):
            plugin_name = step.get("plugin")
            if not plugin_name:
                raise ValueError(f"Step {i}: Missing 'plugin' field")

            step_result = self._execute_plugin_step(
                plugin_name, step, config_context, data_hub, i
            )

            results[f"step_{i}_result"] = step_result

        return results

    def run_single_plugin(
        self, plugin_name: str, config_overrides: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a single plugin with intelligent auto-discovery.

        This method provides a lightweight way to run individual plugins without
        defining a full pipeline. It's ideal for:
        - Testing plugins in isolation
        - Quick data exploration and prototyping
        - Running ad-hoc data processing tasks
        - Plugin development and debugging

        **Smart Case Context Resolution**:
            The method intelligently handles case configuration:
            1. If case.yaml exists: Load and use existing configuration
            2. If no case.yaml: Auto-discover data files in case directory
            3. Create minimal configuration context for execution

        **Auto-Discovery Behavior**:
            When case.yaml doesn't exist, the engine automatically:
            - Scans case directory for data files (CSV, JSON, Parquet, Excel, XML)
            - Creates logical data source names from filenames
            - Registers discovered sources in DataHub
            - Makes them available to plugin via dependency injection

        **Configuration Hierarchy**:
            Even in single-plugin mode, full configuration hierarchy applies:
            CLI overrides > Case config > Global config > Plugin defaults

        Args:
            plugin_name (str): Name of the plugin to execute.
                Must match the name specified in @plugin decorator.
                Case-sensitive. Spaces allowed.
                Example: "Data Generator", "CSV Validator", "Feature Engineer"

            config_overrides (Optional[Dict[str, Any]], optional): Configuration overrides
                for the plugin. Applied with highest precedence.
                Can use either flat or nested format:
                - Flat: {"num_rows": 1000, "seed": 42}
                - Nested: {"plugins": {"Data Generator": {"num_rows": 1000}}}
                Defaults to None.

        Returns:
            Any: Plugin execution result. Type depends on plugin implementation.
                Common return types:
                - pandas.DataFrame: For data processing plugins
                - Dict[str, Any]: For analysis/reporting plugins
                - List: For data collection plugins
                - None: For side-effect-only plugins (e.g., file writers)

        Raises:
            PluginNotFoundError: If plugin_name doesn't match any registered plugin.
                Error message includes list of available plugins.

            FileNotFoundError: If neither case.yaml nor data files exist in case directory.

            ValidationError: If configuration doesn't match plugin's expected schema.

            PluginExecutionError: If plugin raises an exception during execution.

        Example:
            >>> from pathlib import Path
            >>> engine = PipelineEngine(
            ...     project_root=Path.cwd(),
            ...     case_dir=Path("cases/analysis")
            ... )
            >>>
            >>> # Run plugin with default configuration
            >>> result = engine.run_single_plugin("Data Generator")
            >>>
            >>> # Run with configuration overrides
            >>> result = engine.run_single_plugin(
            ...     "Data Generator",
            ...     config_overrides={"num_rows": 5000, "seed": 42}
            ... )
            >>>
            >>> # Run with nested overrides (alternative format)
            >>> result = engine.run_single_plugin(
            ...     "Data Generator",
            ...     config_overrides={
            ...         "plugins": {
            ...             "Data Generator": {
            ...                 "num_rows": 5000,
            ...                 "seed": 42
            ...             }
            ...         }
            ...     }
            ... )

        Auto-Discovery Example:
            Consider a case directory with:
            ```
            cases/analysis/
            ├── data/
            │   ├── transactions.csv
            │   └── customers.json
            └── (no case.yaml)
            ```

            When you run:
            ```python
            result = engine.run_single_plugin("Data Validator")
            ```

            The engine automatically:
            1. Discovers "transactions.csv" → creates source "transactions"
            2. Discovers "customers.json" → creates source "customers"
            3. Makes both available to Data Validator plugin
            4. Plugin can access via: `ctx.datahub.get("transactions")`

        Use Cases:
            **Plugin Development**:
                ```python
                # Quick iteration during development
                result = engine.run_single_plugin("My New Plugin", {"debug": True})
                ```

            **Data Exploration**:
                ```python
                # Explore data without defining pipeline
                df = engine.run_single_plugin("Data Profiler")
                print(df.describe())
                ```

            **Ad-hoc Processing**:
                ```python
                # One-off data transformation
                cleaned = engine.run_single_plugin(
                    "Data Cleaner",
                    {"remove_outliers": True, "fill_na": "mean"}
                )
                ```

        Note:
            - Auto-discovery scans case directory recursively for data files
            - Discovered sources use filename (without extension) as logical name
            - If multiple files have same name, numeric suffixes are added
            - Case directory is created if it doesn't exist
            - No pipeline definition needed - just run the plugin
        """
        config_overrides = config_overrides or {}

        # Load global configuration
        global_config = load_yaml(self.project_root / "config" / "global.yaml")

        # Try to load existing case configuration
        case_config = {}
        case_config_path = self.case_dir / "case.yaml"
        if case_config_path.exists():
            self.logger.info(f"Loading existing case config: {case_config_path}")
            case_config = load_yaml(case_config_path)
        else:
            self.logger.info(
                f"No case.yaml found, using minimal configuration for single plugin execution"
            )
            # Create minimal case config for single plugin execution
            case_config = {
                "case_info": {
                    "name": f"Single Plugin Execution: {plugin_name}",
                    "description": f"Temporary case context for running {plugin_name}",
                },
                "data_sources": self._auto_discover_data_sources(),
            }

        # Create configuration context with proper hierarchy
        config_context = create_configuration_context(
            global_config=global_config,
            case_config=case_config,
            cli_overrides=config_overrides,
            plugin_registry=PLUGIN_REGISTRY,
        )

        # Create DataHub
        data_hub = DataHub(self.case_dir, self.logger)

        # Register global data sources (if any)
        global_data_sources = case_config.get("data_sources", {})
        if global_data_sources:
            data_hub.register_global_sources(global_data_sources)

        # Execute plugin
        self.logger.info(f"Executing plugin: {plugin_name}")
        return self._execute_plugin_step(plugin_name, {}, config_context, data_hub, 1)

    def _execute_plugin_step(
        self,
        plugin_name: str,
        step_config: Dict[str, Any],
        config_context: Dict[str, Any],
        data_hub: DataHub,
        step_number: int,
    ) -> Any:
        """
        Execute a single plugin step with automatic I/O handling.

        Automatically:
        1. Extracts DataSource/DataSink from plugin config
        2. Registers and loads DataSource inputs
        3. Executes the plugin
        4. Saves results to DataSink outputs
        """
        self.logger.info(f"Step {step_number}: {plugin_name}")

        # Get plugin specification
        plugin_spec = get_plugin(plugin_name)

        # Get plugin configuration
        plugin_config = get_plugin_configuration(
            plugin_name,
            config_context,
            step_config.get("config", {}),
            plugin_spec.config_model,
        )

        # Extract I/O metadata from config
        io_metadata = self._extract_io_metadata(plugin_config)

        # Register and resolve DataSource inputs
        self._register_data_sources(io_metadata["sources"], data_hub)

        # Create plugin context
        plugin_context = PluginContext(
            datahub=data_hub,
            logger=self.logger,
            project_root=self.project_root,
            case_path=self.case_dir,
            config=plugin_config,
        )

        # Execute plugin
        result = plugin_spec.func(plugin_context)

        # Save results to DataSink outputs
        self._save_to_sinks(io_metadata["sinks"], result, data_hub)

        return result

    def _extract_io_metadata(self, config) -> Dict[str, List[tuple]]:
        """
        Extract DataSource and DataSink metadata from plugin config.

        Returns:
            Dictionary with 'sources' and 'sinks' lists containing tuples of
            (field_name, config_value, metadata_object)
        """
        if config is None:
            return {"sources": [], "sinks": []}

        type_hints = get_type_hints(type(config), include_extras=True)

        sources = []
        sinks = []

        for field_name, field_type in type_hints.items():
            if not hasattr(field_type, "__metadata__"):
                continue

            field_value = getattr(config, field_name)

            for metadata in field_type.__metadata__:
                if isinstance(metadata, DataSource):
                    sources.append((field_name, field_value, metadata))
                elif isinstance(metadata, DataSink):
                    sinks.append((field_name, field_value, metadata))

        return {"sources": sources, "sinks": sinks}

    def _register_data_sources(self, sources: List[tuple], datahub: DataHub):
        """
        Register all DataSource fields in DataHub.

        Uses hybrid path resolution to support both logical names and direct paths.
        """
        for field_name, config_value, metadata in sources:
            # Resolve path (logical name or direct path)
            physical_path = datahub.resolve_path(config_value)

            # Resolve handler
            handler_type = datahub.resolve_handler(config_value, metadata.handler)

            # Resolve additional handler args
            handler_args = datahub.resolve_handler_args(config_value)
            handler_args.update(metadata.handler_args)

            # Register in DataHub
            datahub.register_source(
                name=field_name,
                path=physical_path,
                handler_type=handler_type,
                must_exist=metadata.required,
                expected_type=metadata.schema,
                **handler_args,
            )

            # Log resolution details
            if config_value.startswith(DataHub.LOGICAL_NAME_PREFIX):
                self.logger.debug(
                    f"  Registered input: {field_name} = {config_value} → {physical_path}"
                )
            elif (
                datahub._is_valid_logical_name_format(config_value)
                and config_value in datahub._data_sources
            ):
                self.logger.debug(
                    f"  Registered input: {field_name} = {config_value} (logical) → {physical_path}"
                )
            else:
                self.logger.debug(f"  Registered input: {field_name} → {physical_path}")

    def _save_to_sinks(self, sinks: List[tuple], result: Any, datahub: DataHub):
        """
        Save plugin results to all DataSink outputs.

        Handles both single-output and multi-output plugins.
        """
        if not sinks:
            self.logger.debug("Plugin has no DataSink outputs, result not saved")
            return

        if len(sinks) == 1:
            # Single output: save result directly
            field_name, config_value, metadata = sinks[0]

            # Resolve path and handler
            physical_path = datahub.resolve_path(config_value)
            handler_type = datahub.resolve_handler(config_value, metadata.handler)

            # Save data
            datahub.save(
                name=field_name,
                data=result,
                path=physical_path,
                handler_type=handler_type,
            )

            # Log save details
            if config_value.startswith(DataHub.LOGICAL_NAME_PREFIX):
                self.logger.info(
                    f"  Saved output: {field_name} = {config_value} → {physical_path}"
                )
            elif (
                datahub._is_valid_logical_name_format(config_value)
                and config_value in datahub._data_sources
            ):
                self.logger.info(
                    f"  Saved output: {field_name} = {config_value} (logical) → {physical_path}"
                )
            else:
                self.logger.info(f"  Saved output: {field_name} → {physical_path}")

        else:
            # Multiple outputs: result must be a dictionary
            if not isinstance(result, dict):
                raise TypeError(
                    f"Plugin declares {len(sinks)} outputs but returned {type(result).__name__}. "
                    f"Multi-output plugins must return a dictionary with keys matching output field names."
                )

            for field_name, config_value, metadata in sinks:
                if field_name not in result:
                    raise KeyError(
                        f"Plugin declares output '{field_name}' but result dictionary does not contain this key. "
                        f"Available keys: {list(result.keys())}"
                    )

                # Resolve path and handler
                physical_path = datahub.resolve_path(config_value)
                handler_type = datahub.resolve_handler(config_value, metadata.handler)

                # Save data
                datahub.save(
                    name=field_name,
                    data=result[field_name],
                    path=physical_path,
                    handler_type=handler_type,
                )

                # Log save details
                if config_value.startswith(DataHub.LOGICAL_NAME_PREFIX):
                    self.logger.info(
                        f"  Saved output: {field_name} = {config_value} → {physical_path}"
                    )
                elif (
                    datahub._is_valid_logical_name_format(config_value)
                    and config_value in datahub._data_sources
                ):
                    self.logger.info(
                        f"  Saved output: {field_name} = {config_value} (logical) → {physical_path}"
                    )
                else:
                    self.logger.info(f"  Saved output: {field_name} → {physical_path}")

    def _auto_discover_data_sources(self) -> Dict[str, Any]:
        """
        Auto-discover data files in case directory as data sources.

        Scans the case directory for common data file formats and creates
        basic data source configurations for them.

        Returns:
            Dictionary of auto-discovered data sources
        """
        discovered_sources = {}

        if not self.case_dir.exists():
            return discovered_sources

        data_dir = self.case_dir / "data"

        # Common file extensions and their handlers
        file_handlers = {
            ".csv": "csv",
            ".json": "json",
            ".parquet": "parquet",
            ".xlsx": "excel",
            ".xml": "xml",
        }

        # Scan case directory and data subdirectory
        scan_dirs = [self.case_dir]
        if data_dir.exists():
            scan_dirs.append(data_dir)

        for scan_dir in scan_dirs:
            for file_path in scan_dir.glob("*"):
                if file_path.is_file():
                    file_ext = file_path.suffix.lower()
                    if file_ext in file_handlers:
                        # Create data source name from filename
                        source_name = file_path.stem

                        # Avoid duplicate names by adding suffix if needed
                        base_name = source_name
                        counter = 1
                        while source_name in discovered_sources:
                            source_name = f"{base_name}_{counter}"
                            counter += 1

                        # Create data source config
                        relative_path = file_path.relative_to(self.case_dir)
                        discovered_sources[source_name] = {
                            "handler": file_handlers[file_ext],
                            "path": str(relative_path),
                        }

        self.logger.debug(
            f"Auto-discovered {len(discovered_sources)} data sources: {list(discovered_sources.keys())}"
        )
        return discovered_sources
