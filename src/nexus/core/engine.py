"""
Pipeline execution engine.

Following data_replay's functional approach with immutable contexts
and clean separation of concerns.
"""

import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, get_type_hints

from .context import NexusContext, PluginContext
from .config import (
    create_configuration_context,
    extract_plugin_defaults,
    get_plugin_configuration,
    merge_data_sources,
    load_yaml,
)
from .datahub import DataHub
from .discovery import (
    PLUGIN_REGISTRY,
    auto_discover_data_sources,
    discover_plugins_from_module,
    discover_plugins_from_directory,
)
from .types import DataSource

logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    Core pipeline execution engine.

    Orchestrates the complete pipeline lifecycle:
    1. Plugin discovery and registration
    2. Configuration resolution
    3. Data source management
    4. Plugin execution with dependency injection
    """

    def __init__(
        self,
        project_root: Path,
        case_path: Path,
        logger_instance: Optional[logging.Logger] = None,
    ):
        self.project_root = project_root
        self.case_path = case_path
        self.logger = logger_instance or logger

        # Create immutable context
        self.context = NexusContext(
            project_root=project_root,
            case_path=case_path,
            logger=self.logger,
        )

        # Initialize components
        self.datahub = self.context.create_datahub()

        # Auto-discover plugins
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        """Discover and register plugins from configured sources."""
        # Load basic configuration to get plugin paths
        global_config_path = self.project_root / "config" / "global.yaml"
        case_config_path = self.case_path / "case.yaml"

        global_config = load_yaml(global_config_path)
        case_config = load_yaml(case_config_path)

        # Get plugin discovery configuration
        plugin_config = global_config.get("plugins", {})
        framework_config = global_config.get("framework", {})

        # Discover from built-in plugins
        builtin_plugins_path = self.project_root / "src" / "nexus" / "plugins"
        if builtin_plugins_path.exists():
            discover_plugins_from_directory(builtin_plugins_path)

        # Discover from configured module paths
        plugin_modules = plugin_config.get("modules", [])
        for module_name in plugin_modules:
            discover_plugins_from_module(module_name)

        # Discover from configured directory paths
        plugin_paths = plugin_config.get("paths", [])
        for path_str in plugin_paths:
            plugin_path = Path(path_str)
            if not plugin_path.is_absolute():
                plugin_path = self.project_root / plugin_path
            discover_plugins_from_directory(plugin_path)

        # Discover from case-specific plugins
        case_plugins_path = self.case_path / "plugins"
        if case_plugins_path.exists():
            discover_plugins_from_directory(case_plugins_path)

        self.logger.info(f"Plugin registry contains {len(PLUGIN_REGISTRY)} plugins")

    def run_pipeline(
        self,
        pipeline_config_path: Optional[Path] = None,
        cli_overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Execute the complete pipeline.

        Args:
            pipeline_config_path: Optional path to pipeline configuration
            cli_overrides: CLI argument overrides
        """
        cli_overrides = cli_overrides or {}

        # Load pipeline configuration
        config_path = pipeline_config_path or (self.case_path / "case.yaml")
        if not config_path.exists():
            raise FileNotFoundError(f"Pipeline configuration not found: {config_path}")

        case_config = load_yaml(config_path)
        pipeline_steps = case_config.get("pipeline", [])

        if not pipeline_steps:
            raise ValueError("No pipeline steps defined in configuration")

        # Auto-discover data sources from active plugins
        active_plugins = [step["plugin"] for step in pipeline_steps]
        discovered_sources = auto_discover_data_sources(active_plugins)

        # Set up data sources
        self._setup_data_sources(discovered_sources, cli_overrides)

        # Execute pipeline steps
        self.logger.info(f"Executing pipeline with {len(pipeline_steps)} steps")
        for i, step in enumerate(pipeline_steps, 1):
            plugin_name = step["plugin"]
            self.logger.info(f"Step {i}/{len(pipeline_steps)}: {plugin_name}")

            step_config = step.get("config", {})
            step_cli_overrides = cli_overrides.get("plugins", {}).get(plugin_name, {})

            self._execute_step(plugin_name, step_config, step_cli_overrides, step)

        self.logger.info("Pipeline execution completed successfully")

    def run_plugin(
        self,
        plugin_name: str,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a single plugin.

        Args:
            plugin_name: Name of the plugin to execute
            config_overrides: Configuration overrides

        Returns:
            Plugin execution result
        """
        if plugin_name not in PLUGIN_REGISTRY:
            raise ValueError(f"Plugin '{plugin_name}' not found in registry")

        plugin_spec = PLUGIN_REGISTRY[plugin_name]
        config_overrides = config_overrides or {}

        self.logger.info(f"Executing plugin: {plugin_name}")

        # Auto-discover data sources for this plugin
        discovered_sources = auto_discover_data_sources([plugin_name])
        self._setup_data_sources(discovered_sources, {})

        # Execute the plugin
        return self._execute_plugin(plugin_spec, config_overrides)

    def _setup_data_sources(
        self, discovered_sources: Dict[str, Dict], cli_overrides: Dict[str, Any]
    ) -> None:
        """Set up data sources in the DataHub."""
        # Load configuration context
        import json

        context = create_configuration_context(
            project_root_str=str(self.project_root),
            case_path_str=str(self.case_path),
            plugin_registry_hash="{}",  # Simplified for now
            discovered_sources_hash=json.dumps(discovered_sources),
            cli_args_hash=json.dumps(cli_overrides),
        )

        # Merge data sources from all configuration layers
        final_sources = merge_data_sources(
            discovered=discovered_sources,
            global_config=context["global_config"],
            case_config=context["case_config"],
            case_path=self.case_path,
            project_root=self.project_root,
        )

        # Register all data sources with the DataHub
        for source_name, source_config in final_sources.items():
            self.datahub.register_source(
                name=source_name,
                path=str(source_config["path"]),
                handler_type=source_config["handler"],
                must_exist=source_config.get("must_exist", True),
            )

    def _execute_step(
        self,
        plugin_name: str,
        step_config: Dict[str, Any],
        cli_overrides: Dict[str, Any],
        step_definition: Dict[str, Any],
    ) -> Any:
        """Execute a single pipeline step."""
        plugin_spec = PLUGIN_REGISTRY[plugin_name]

        # Merge configuration overrides
        merged_overrides = step_config.copy()
        merged_overrides.update(cli_overrides)

        # Execute the plugin
        result = self._execute_plugin(plugin_spec, merged_overrides)

        # Handle output saving
        outputs = step_definition.get("outputs", [])
        if result is not None and outputs:
            for output in outputs:
                output_name = output["name"]
                self.datahub.save(output_name, result)
                self.logger.info(f"Saved output to '{output_name}'")

        return result

    def _execute_plugin(
        self, plugin_spec, config_overrides: Dict[str, Any]
    ) -> Any:
        """Execute a plugin with dependency injection."""
        # Load configuration context
        import json

        context = create_configuration_context(
            project_root_str=str(self.project_root),
            case_path_str=str(self.case_path),
            plugin_registry_hash="{}",
            discovered_sources_hash="{}",
            cli_args_hash=json.dumps(config_overrides),
        )

        # Get plugin defaults and calculate final configuration
        plugin_defaults = extract_plugin_defaults(PLUGIN_REGISTRY)
        plugin_config = get_plugin_configuration(
            plugin_name=plugin_spec.name,
            plugin_spec=plugin_spec,
            case_config=context["case_config"],
            global_config=context["global_config"],
            plugin_defaults=plugin_defaults,
            cli_overrides=config_overrides,
        )

        # Hydrate configuration with data sources
        if plugin_spec.config_model:
            hydrated_config = self._hydrate_config(plugin_spec, plugin_config)
            config_instance = plugin_spec.config_model(**hydrated_config)
        else:
            config_instance = None

        # Create plugin context
        plugin_context = PluginContext.from_nexus_context(
            nexus_context=self.context,
            datahub=self.datahub,
            config=config_instance,
        )

        # Execute plugin with dependency injection
        return self._inject_and_execute(plugin_spec, plugin_context, config_instance)

    def _hydrate_config(self, plugin_spec, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Hydrate configuration by injecting data sources."""
        if not plugin_spec.config_model:
            return config_dict

        hydrated_config = config_dict.copy()

        try:
            type_hints = get_type_hints(plugin_spec.config_model, include_extras=True)
        except (NameError, TypeError):
            return hydrated_config

        for field_name, field_type in type_hints.items():
            # Find DataSource annotations
            if hasattr(field_type, "__metadata__"):
                for metadata in field_type.__metadata__:
                    if isinstance(metadata, DataSource):
                        try:
                            data = self.datahub.get(metadata.name)
                            hydrated_config[field_name] = data
                            self.logger.debug(
                                f"Hydrated field '{field_name}' with data source '{metadata.name}'"
                            )
                        except (KeyError, FileNotFoundError) as e:
                            self.logger.warning(
                                f"Could not load data source '{metadata.name}': {e}"
                            )

        return hydrated_config

    def _inject_and_execute(self, plugin_spec, plugin_context, config_instance) -> Any:
        """Execute plugin function with dependency injection."""
        try:
            # Analyze function signature for dependency injection
            sig = inspect.signature(plugin_spec.func)
            kwargs = {}

            for param_name, param in sig.parameters.items():
                if param_name == "context":
                    kwargs["context"] = plugin_context
                elif param_name == "config" and config_instance is not None:
                    kwargs["config"] = config_instance
                elif param_name == "logger":
                    kwargs["logger"] = self.logger
                elif param_name == "datahub":
                    kwargs["datahub"] = self.datahub

            return plugin_spec.func(**kwargs)

        except Exception as e:
            self.logger.error(f"Plugin '{plugin_spec.name}' failed: {e}")
            raise