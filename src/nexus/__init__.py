"""
Nexus - A modern data processing framework.

Simplified architecture with clear concepts:
- Case = Complete workspace (data + configuration)
- Template = Reusable pipeline definition
- Clean copy/reference semantics
"""

from .core.case_manager import CaseManager
from .core.context import NexusContext, PluginContext
from .core.datahub import DataHub
from .core.discovery import get_plugin, list_plugins, plugin
from .core.engine import PipelineEngine
from .core.types import DataSink, DataSource, PluginConfig
from .main import create_engine, run_pipeline, run_plugin

__version__ = "0.3.0"
__all__ = [
    "NexusContext",
    "PluginContext",
    "DataHub",
    "PipelineEngine",
    "CaseManager",
    "plugin",
    "get_plugin",
    "list_plugins",
    "DataSource",
    "DataSink",
    "PluginConfig",
    "create_engine",
    "run_pipeline",
    "run_plugin",
]
