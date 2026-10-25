"""Renderer protocol, context and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar, Generic, TypeVar

import numpy as np
from pydantic import Field

from ..errors import RendererError
from ..models import RendererSpec, ReproModel, SensorMatch


class RenderContext(ReproModel):
    """All information a renderer needs for one frame."""

    frame_index: int
    timestamp_ms: float
    sensors: dict[str, SensorMatch | None] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


ConfigT = TypeVar("ConfigT", bound=ReproModel)


class Renderer(ABC, Generic[ConfigT]):
    """A drawing component that mutates or returns one BGR frame."""

    name: ClassVar[str] = ""
    Config: ClassVar[type[ConfigT]]

    def __init__(self, config: ConfigT) -> None:
        self.config = config

    @classmethod
    def from_config(cls, config: dict[str, Any] | ConfigT | None) -> Renderer[ConfigT]:
        validated = config if isinstance(config, ReproModel) else cls.Config.model_validate(config or {})
        return cls(validated)

    @abstractmethod
    def render(self, frame: np.ndarray, context: RenderContext) -> np.ndarray:
        """Draw on *frame* and return the resulting frame."""


class RendererRegistry:
    """Maps renderer type names to classes."""

    def __init__(self) -> None:
        self._types: dict[str, type[Renderer[Any]]] = {}

    def register(self, name: str, renderer_type: type[Renderer[Any]], *, replace: bool = False) -> None:
        if not name:
            raise RendererError("renderer type name must not be empty")
        if not (isinstance(renderer_type, type) and issubclass(renderer_type, Renderer)):
            raise RendererError(f"renderer '{name}' must inherit from Renderer")
        existing = self._types.get(name)
        if existing is not None and not replace and existing is not renderer_type:
            raise RendererError(f"renderer type '{name}' is already registered by {existing.__module__}")
        self._types[name] = renderer_type
        if not renderer_type.name:
            renderer_type.name = name

    def get(self, name: str) -> type[Renderer[Any]]:
        try:
            return self._types[name]
        except KeyError:
            available = ", ".join(sorted(self._types)) or "(none)"
            raise RendererError(f"renderer type '{name}' is not registered; available: {available}") from None

    def create(self, spec: RendererSpec) -> Renderer[Any]:
        renderer_type = self.get(spec.type)
        try:
            config = renderer_type.Config.model_validate(spec.config or {})
        except Exception as exc:
            raise RendererError(f"invalid config for renderer '{spec.type}': {exc}") from exc
        return renderer_type(config)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._types))

    def list(self) -> list[type[Renderer[Any]]]:
        return [self._types[name] for name in self.names()]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._types

    def __len__(self) -> int:
        return len(self._types)


default_renderer_registry = RendererRegistry()


def register_renderer(name: str, *, replace: bool = False) -> Callable[[type[Renderer[Any]]], type[Renderer[Any]]]:
    """Register a renderer class under a stable YAML type name."""

    def decorator(renderer_type: type[Renderer[Any]]) -> type[Renderer[Any]]:
        default_renderer_registry.register(name, renderer_type, replace=replace)
        return renderer_type

    return decorator
