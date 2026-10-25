"""Built-in repro renderers and the registry API."""

from __future__ import annotations

from .base import (
    RenderContext,
    Renderer,
    RendererRegistry,
    default_renderer_registry,
    register_renderer,
)
from .frame_info import FrameInfoRenderer
from .speed import SpeedRenderer
from .targets import TargetRenderer

__all__ = [
    "RenderContext",
    "Renderer",
    "RendererRegistry",
    "default_renderer_registry",
    "register_renderer",
    "FrameInfoRenderer",
    "SpeedRenderer",
    "TargetRenderer",
]
