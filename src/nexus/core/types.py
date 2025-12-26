"""
Core type definitions and annotations for the Nexus framework.

Following data_replay's approach of clear type definitions with
functional programming principles.
"""

from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel


class PluginConfig(BaseModel):
    """
    Base class for plugin configuration models.

    All plugin configurations inherit from this to ensure
    proper validation and type safety.
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}


class PluginSpec:
    """
    Specification for a registered plugin.

    Contains all metadata needed to execute a plugin,
    following data_replay's plugin specification pattern.
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        config_model: Optional[type[PluginConfig]] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ):
        self.name = name
        self.func = func
        self.config_model = config_model
        self.description = description or (func.__doc__ if func.__doc__ else "")
        self.tags = tags or []
        self.metadata: Dict[str, Any] = {}

    def with_metadata(self, **kwargs: Any) -> "PluginSpec":
        """Return a new PluginSpec with merged metadata."""
        spec = PluginSpec(
            name=self.name,
            func=self.func,
            config_model=self.config_model,
            description=self.description,
            tags=self.tags,
        )
        spec.metadata = {**self.metadata, **kwargs}
        return spec
