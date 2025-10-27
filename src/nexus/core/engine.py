"""
Pipeline execution engine focused on plugin orchestration.

The engine loads pipeline definitions, resolves configuration, and executes
plugins sequentially while sharing in-memory state between steps.
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
from .context import NexusContext
from .discovery import PLUGIN_REGISTRY, discover_all_plugins, get_plugin

logger = logging.getLogger(__name__)


class PipelineEngine:
    """Simple plugin orchestrator."""

    def __init__(self, project_root: Path, case_dir: Path):
        self.project_root = project_root
        self.case_dir = case_dir
        self.logger = logger

        discover_all_plugins(self.project_root)

    def run_pipeline(
        self,
        case_config: Dict[str, Any],
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute all steps defined in a case configuration."""

        config_overrides = config_overrides or {}
        global_config = load_global_configuration(self.project_root)

        config_context = create_configuration_context(
            global_config=global_config,
            case_config=case_config,
            cli_overrides=config_overrides,
            plugin_registry=PLUGIN_REGISTRY,
        )

        nexus_ctx = NexusContext(
            project_root=self.project_root,
            case_path=self.case_dir,
            logger=self.logger,
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
            step_config: Dict[str, Any] = step.get("config", {})

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

            self.logger.info(f"Executing plugin: {plugin_name}")
            step_result = plugin_spec.func(plugin_ctx)
            shared_state["last_result"] = step_result
            results[f"step_{idx}_result"] = step_result

        return results

    def run_single_plugin(
        self,
        plugin_name: str,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a single plugin with optional configuration overrides."""

        config_overrides = config_overrides or {}
        global_config = load_global_configuration(self.project_root)

        case_config = {}
        case_config_path = self.case_dir / "case.yaml"
        if case_config_path.exists():
            case_config = load_yaml(case_config_path)

        config_context = create_configuration_context(
            global_config=global_config,
            case_config=case_config,
            cli_overrides={"plugins": {plugin_name: config_overrides}},
            plugin_registry=PLUGIN_REGISTRY,
        )

        nexus_ctx = NexusContext(
            project_root=self.project_root,
            case_path=self.case_dir,
            logger=self.logger,
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

        self.logger.info(f"Executing plugin: {plugin_name}")
        return plugin_spec.func(plugin_ctx)

    # ------------------------------------------------------------------
    # Helpers

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
