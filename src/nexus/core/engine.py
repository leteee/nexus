"""
Simplified Pipeline execution engine.

Clean, focused execution with case-based data path resolution.
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
    Simplified pipeline execution engine.

    Key concepts:
    - All data paths resolved relative to case directory
    - Clean configuration hierarchy: global → case → CLI overrides
    - No complex template management at runtime
    """

    def __init__(self, project_root: Path, case_dir: Path):
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
        """Discover plugins from various sources."""
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
        plugin_paths = global_config.get("plugins", {}).get("paths", [])
        if plugin_paths:
            discover_plugins_from_paths([self.project_root / p for p in plugin_paths])

        # Discover handlers
        handlers_dir = self.project_root / "src" / "nexus" / "core"
        discover_handlers_from_paths([handlers_dir], self.project_root)

        self.logger.info(f"Plugin registry contains {len(PLUGIN_REGISTRY)} plugins")

    def run_pipeline(
        self,
        pipeline_config: Dict[str, Any],
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute complete pipeline.

        Args:
            pipeline_config: Pipeline configuration (from case.yaml or template)
            config_overrides: CLI configuration overrides

        Returns:
            Dictionary of all pipeline outputs
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
        Execute a single plugin with intelligent case configuration loading.

        This method implements smart case context resolution:
        1. Load existing case.yaml if present in case directory
        2. Auto-discover data files in case directory as data sources
        3. Create minimal configuration context for plugin execution

        Args:
            plugin_name: Name of plugin to execute
            config_overrides: Configuration overrides

        Returns:
            Plugin execution result
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
