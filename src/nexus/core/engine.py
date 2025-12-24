"""
Pipeline execution engine focused on plugin orchestration.

The engine loads pipeline definitions, resolves configuration references,
and executes plugins sequentially while sharing in-memory state between steps.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    create_configuration_context,
    get_plugin_configuration,
    load_global_configuration,
    load_yaml,
)
from .config_resolver import resolve_config, ConfigResolutionError
from .context import NexusContext
from .discovery import PLUGIN_REGISTRY, discover_all_plugins, get_plugin

logger = logging.getLogger(__name__)


class PipelineEngine:
    """Simple plugin orchestrator."""

    def __init__(self, project_root: Path, case_dir: Path):
        self.project_root = project_root
        self.case_dir = case_dir

        discover_all_plugins(self.project_root)

    def run_pipeline(
        self,
        case_config: Dict[str, Any],
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute all steps defined in a case configuration.

        Resolves configuration references (@defaults.xxx) before executing plugins.
        """
        config_overrides = config_overrides or {}
        global_config = load_global_configuration(self.project_root)

        # Merge defaults from global and case configs
        defaults = self._merge_defaults(global_config, case_config)

        config_context = create_configuration_context(
            global_config=global_config,
            case_config=case_config,
            cli_overrides=config_overrides,
            plugin_registry=PLUGIN_REGISTRY,
        )

        nexus_ctx = NexusContext(
            project_root=self.project_root,
            case_path=self.case_dir,
            run_config=config_context,
        )

        shared_state: Dict[str, Any] = {}
        results: Dict[str, Any] = {}

        steps: List[Dict[str, Any]] = case_config.get("pipeline", [])
        if not steps:
            raise ValueError("Pipeline configuration must contain a 'pipeline' list")

        for idx, step in enumerate(steps, start=1):
            if "plugin" not in step:
                raise ValueError(f"Pipeline step {idx} missing 'plugin' key")

            plugin_name: str = step["plugin"]

            # Check if plugin is enabled (default: true)
            if not step.get("enable", True):
                logger.info(f"Skipping disabled plugin (step {idx}): {plugin_name}")
                continue

            step_config: Dict[str, Any] = step.get("config", {})

            # Resolve configuration references
            try:
                step_config = resolve_config(step_config, defaults)
            except ConfigResolutionError as e:
                raise ValueError(
                    f"Failed to resolve config for plugin '{plugin_name}' at step {idx}: {e}"
                ) from e

            plugin_spec = get_plugin(plugin_name)
            plugin_cfg = self._build_plugin_config(
                plugin_spec.name,
                plugin_spec.config_model,
                config_context,
                step_config,
            )

            plugin_ctx = nexus_ctx.create_plugin_context(
                config=plugin_cfg,
                shared_state=shared_state,
            )

            logger.info(f"Executing plugin: {plugin_name}")
            step_result = plugin_spec.func(plugin_ctx)
            shared_state["last_result"] = step_result
            results[f"step_{idx}_result"] = step_result

        return results

    def run_single_plugin(
        self,
        plugin_name: str,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a single plugin with optional configuration overrides.

        Resolves configuration references (@defaults.xxx) before executing.
        """
        config_overrides = config_overrides or {}
        global_config = load_global_configuration(self.project_root)

        case_config = {}
        case_config_path = self.case_dir / "case.yaml"
        if case_config_path.exists():
            case_config = load_yaml(case_config_path)

        # Merge defaults from global and case configs
        defaults = self._merge_defaults(global_config, case_config)

        # Resolve configuration references
        try:
            config_overrides = resolve_config(config_overrides, defaults)
        except ConfigResolutionError as e:
            raise ValueError(
                f"Failed to resolve config for plugin '{plugin_name}': {e}"
            ) from e

        config_context = create_configuration_context(
            global_config=global_config,
            case_config=case_config,
            cli_overrides={"plugins": {plugin_name: config_overrides}},
            plugin_registry=PLUGIN_REGISTRY,
        )

        nexus_ctx = NexusContext(
            project_root=self.project_root,
            case_path=self.case_dir,
            run_config=config_context,
        )

        plugin_spec = get_plugin(plugin_name)
        plugin_cfg = self._build_plugin_config(
            plugin_spec.name,
            plugin_spec.config_model,
            config_context,
            config_overrides,
        )

        plugin_ctx = nexus_ctx.create_plugin_context(
            config=plugin_cfg,
            shared_state={},
        )

        logger.info(f"Executing plugin: {plugin_name}")
        return plugin_spec.func(plugin_ctx)

    # ------------------------------------------------------------------
    # Helpers

    def _merge_defaults(
        self,
        global_config: Dict[str, Any],
        case_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge defaults from global and case configurations.

        Case defaults override global defaults.

        Args:
            global_config: Global configuration
            case_config: Case configuration

        Returns:
            Merged defaults dictionary
        """
        global_defaults = global_config.get("defaults", {})
        case_defaults = case_config.get("defaults", {})

        # Case defaults override global defaults
        merged = {**global_defaults, **case_defaults}
        return merged

    def _build_plugin_config(
        self,
        plugin_name: str,
        config_model: Optional[type],
        config_context: Dict[str, Any],
        step_config: Dict[str, Any],
    ) -> Optional[Any]:
        if not config_model:
            return None

        return get_plugin_configuration(
            plugin_name=plugin_name,
            config_context=config_context,
            step_config=step_config,
            config_model=config_model,
        )
