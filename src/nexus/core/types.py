"""
Core type definitions and annotations for the Nexus framework.

Following data_replay's approach of clear type definitions with
functional programming principles.
"""

from typing import Annotated, Any, Dict, Optional, Protocol, runtime_checkable
from pathlib import Path
from pydantic import BaseModel


class DataSource:
    """
    Annotation for data input dependencies.

    Used with Annotated types to declare data requirements.
    The framework automatically loads and injects the specified data.
    """

    def __init__(self, name: str, handler_args: Optional[Dict[str, Any]] = None):
        self.name = name
        self.handler_args = handler_args or {}


class DataSink:
    """
    Annotation for data output destinations.

    Used with Annotated types to declare where plugin outputs should be saved.
    The framework automatically saves plugin results to the specified location.
    """

    def __init__(self, name: str, handler_args: Optional[Dict[str, Any]] = None):
        self.name = name
        self.handler_args = handler_args or {}


class PluginConfig(BaseModel):
    """
    Base class for plugin configuration models.

    All plugin configurations inherit from this to ensure
    proper validation and type safety.
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}


@runtime_checkable
class DataHandler(Protocol):
    """
    Protocol for data handlers.

    Defines the interface that all data handlers must implement.
    Following data_replay's handler pattern.
    """

    def load(self, path: Path) -> Any:
        """Load data from the specified path."""
        ...

    def save(self, data: Any, path: Path) -> None:
        """Save data to the specified path."""
        ...

    @property
    def produced_type(self) -> type:
        """Return the type of data this handler produces."""
        ...


class PluginSpec:
    """
    Specification for a registered plugin.

    Contains all metadata needed to execute a plugin,
    following data_replay's plugin specification pattern.
    """

    def __init__(
        self,
        name: str,
        func: callable,
        config_model: Optional[type[PluginConfig]] = None,
        description: Optional[str] = None,
        output_key: Optional[str] = None
    ):
        self.name = name
        self.func = func
        self.config_model = config_model
        self.description = description or func.__doc__
        self.output_key = output_key