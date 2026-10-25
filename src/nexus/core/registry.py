"""Node definitions, decorator and registry.

Nodes are the executable units of a flow.  A node pack is a regular Python
module that imports :func:`node` and decorates functions; the engine imports
configured modules (and optional ``nexus.nodes`` entry points) and validates
inputs with Pydantic before invoking a node.
"""

from __future__ import annotations

import difflib
import importlib
import inspect
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.metadata import entry_points
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from .errors import NodeLoadError, NodeNotFoundError
from .models import NODE_NAME_PATTERN, NexusModel

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "nexus.nodes"


class NodeInput(NexusModel):
    """Base class for typed node input models."""


def _validate_node_name(name: str) -> str:
    if not NODE_NAME_PATTERN.match(name):
        raise ValueError(
            f"invalid node name '{name}'; use letters, digits, dots, underscores or dashes"
        )
    return name


@dataclass(frozen=True)
class NodeSpec:
    """Immutable description of a registered node."""

    name: str
    func: Callable[..., Any]
    input_model: type[BaseModel] | None = None
    output_model: type[BaseModel] | None = None
    description: str = ""
    tags: tuple[str, ...] = ()
    version: str = "1.0"
    source: str = ""
    is_async: bool = False

    def __post_init__(self) -> None:
        _validate_node_name(self.name)
        if self.input_model is not None and not (
            inspect.isclass(self.input_model) and issubclass(self.input_model, BaseModel)
        ):
            raise TypeError(f"input model for node '{self.name}' must be a Pydantic BaseModel subclass")
        if self.output_model is not None and not (
            inspect.isclass(self.output_model) and issubclass(self.output_model, BaseModel)
        ):
            raise TypeError(f"output model for node '{self.name}' must be a Pydantic BaseModel subclass")

    def validate_inputs(self, raw: dict[str, Any]) -> BaseModel | dict[str, Any]:
        if self.input_model is None:
            return raw
        return self.input_model.model_validate(raw)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "version": self.version,
            "source": self.source,
            "has_input_schema": self.input_model is not None,
        }


# Global definitions are populated by the @node decorator.  Registries copy
# from here so tests can create isolated registries without re-importing packs.
_DEFINITIONS: dict[str, NodeSpec] = {}


def _add_definition(spec: NodeSpec, *, replace: bool = False) -> None:
    existing = _DEFINITIONS.get(spec.name)
    if existing is not None and not replace:
        if existing.func is spec.func:
            return
        raise NodeLoadError(
            spec.source or "unknown",
            f"node '{spec.name}' is already defined by {existing.source or 'another module'}",
        )
    _DEFINITIONS[spec.name] = spec


def node(
    name: str,
    *,
    inputs: type[BaseModel] | None = None,
    outputs: type[BaseModel] | None = None,
    description: str | None = None,
    tags: Iterable[str] = (),
    version: str = "1.0",
    registry: NodeRegistry | None = None,
    replace: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a function as a Nexus node.

    The decorated function must accept ``(ctx, inputs)`` where ``inputs`` is a
    validated Pydantic model (or a plain dict when ``inputs=None``).  It may be
    a regular function or an ``async def`` function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        module = getattr(func, "__module__", "")
        qualname = getattr(func, "__qualname__", getattr(func, "__name__", "?"))
        source = f"{module}:{qualname}" if module else qualname
        doc = description if description is not None else (inspect.getdoc(func) or "")
        spec = NodeSpec(
            name=name,
            func=func,
            input_model=inputs,
            output_model=outputs,
            description=doc.strip(),
            tags=tuple(tags),
            version=version,
            source=source,
            is_async=inspect.iscoroutinefunction(func),
        )
        _add_definition(spec, replace=replace)
        if registry is not None:
            registry.add(spec, replace=replace)
        return func

    return decorator


class NodeRegistry:
    """A mutable collection of :class:`NodeSpec` objects."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeSpec] = {}
        self._loaded_modules: set[str] = set()
        self._loaded_entry_points: set[str] = set()
        self.load_errors: list[NodeLoadError] = []

    # -- registration -----------------------------------------------------

    def add(self, spec: NodeSpec, *, replace: bool = False) -> None:
        if spec.name in self._nodes and not replace:
            existing = self._nodes[spec.name]
            if existing.func is spec.func:
                return
            raise NodeLoadError(
                spec.source or "registry",
                f"node '{spec.name}' conflicts with {existing.source or 'existing definition'}",
            )
        self._nodes[spec.name] = spec

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        inputs: type[BaseModel] | None = None,
        outputs: type[BaseModel] | None = None,
        description: str | None = None,
        tags: Iterable[str] = (),
        version: str = "1.0",
        replace: bool = False,
    ) -> NodeSpec:
        source = f"{func.__module__}:{func.__qualname__}"
        spec = NodeSpec(
            name=name,
            func=func,
            input_model=inputs,
            output_model=outputs,
            description=(description if description is not None else inspect.getdoc(func) or "").strip(),
            tags=tuple(tags),
            version=version,
            source=source,
            is_async=inspect.iscoroutinefunction(func),
        )
        _add_definition(spec, replace=replace)
        self.add(spec, replace=replace)
        return spec

    # -- lookup -----------------------------------------------------------

    def get(self, name: str) -> NodeSpec:
        try:
            return self._nodes[name]
        except KeyError:
            matches = difflib.get_close_matches(name, self._nodes, n=3, cutoff=0.5)
            hint = f" Did you mean: {', '.join(matches)}?" if matches else ""
            if self.load_errors:
                failed = ", ".join(error.source for error in self.load_errors)
                hint += f" Some optional node packs could not be loaded ({failed}); run 'nexus nodes list' for details."
            raise NodeNotFoundError(f"node '{name}' is not registered.{hint}") from None

    def has(self, name: str) -> bool:
        return name in self._nodes

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._nodes

    def names(self) -> list[str]:
        return sorted(self._nodes)

    def list(self, *, tag: str | None = None) -> list[NodeSpec]:
        specs = [self._nodes[name] for name in self.names()]
        if tag:
            specs = [spec for spec in specs if tag in spec.tags]
        return specs

    def __len__(self) -> int:
        return len(self._nodes)

    # -- loading ----------------------------------------------------------

    def _copy_definitions(self, *, module_prefix: str | None = None) -> None:
        for spec in _DEFINITIONS.values():
            if module_prefix and not spec.source.startswith(module_prefix):
                continue
            if spec.name not in self._nodes:
                self._nodes[spec.name] = spec

    def load_module(self, module_name: str) -> ModuleType:
        if module_name in self._loaded_modules:
            return importlib.import_module(module_name)
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise NodeLoadError(module_name, f"{type(exc).__name__}: {exc}") from exc
        self._loaded_modules.add(module_name)
        self._copy_definitions(module_prefix=module_name)
        self._copy_definitions()
        logger.debug("Loaded node module %s", module_name)
        return module

    def load_builtin(self) -> None:
        self.load_module("nexus.nodes")

    def load_configured(self, modules: Iterable[str]) -> None:
        for module_name in dict.fromkeys(modules):
            if not module_name:
                continue
            self.load_module(module_name)

    def load_entry_points(self, group: str = ENTRY_POINT_GROUP) -> None:
        try:
            selected = entry_points(group=group)
        except Exception as exc:  # pragma: no cover - platform dependent
            logger.debug("Could not enumerate entry points: %s", exc)
            return

        for entry_point in selected:
            if entry_point.name in self._loaded_entry_points:
                continue
            self._loaded_entry_points.add(entry_point.name)
            try:
                loaded = entry_point.load()
                if inspect.ismodule(loaded):
                    self.load_module(loaded.__name__)
                elif callable(loaded):
                    loaded()
                    self._copy_definitions()
                else:
                    raise TypeError(f"entry point resolved to unsupported object {type(loaded).__name__}")
                logger.debug("Loaded node pack from entry point '%s'", entry_point.name)
            except Exception as exc:
                error = NodeLoadError(f"entry point:{entry_point.name}", f"{type(exc).__name__}: {exc}")
                self.load_errors.append(error)
                logger.debug("Skipping optional node pack '%s': %s", entry_point.name, exc)

    def load_all(self, *, modules: Iterable[str] = (), entry_points_enabled: bool = True) -> None:
        self.load_builtin()
        self.load_configured(modules)
        if entry_points_enabled:
            self.load_entry_points()

    def reset(self) -> None:
        self._nodes.clear()
        self._loaded_modules.clear()
        self._loaded_entry_points.clear()
        self.load_errors.clear()


default_registry = NodeRegistry()


def get_default_registry() -> NodeRegistry:
    return default_registry


def list_defined_nodes() -> dict[str, NodeSpec]:
    """Return every node definition discovered so far (before registry filtering)."""

    return dict(_DEFINITIONS)
