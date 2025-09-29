"""
Nexus - A modern data processing framework.

Following data_replay's design principles with improvements:
- Functional configuration management
- Immutable contexts
- Type-safe plugin system
- Automatic dependency discovery
"""

from .core.context import NexusContext, PluginContext
from .core.datahub import DataHub
from .core.discovery import plugin, get_plugin, list_plugins
from .core.engine import PipelineEngine
from .core.types import DataSource, DataSink, PluginConfig
from .main import create_engine, run_pipeline, run_plugin

__version__ = "0.2.0"
__all__ = [
    "NexusContext",
    "PluginContext",
    "DataHub",
    "PipelineEngine",
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