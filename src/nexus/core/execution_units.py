"""
Unified Execution Unit Framework for Nexus.

Core Philosophy:
    All executable code units (plugins, renderers, validators, etc.) are
    fundamentally the same - they are "execution units" with different
    interface specifications and execution patterns.

Key Concepts:
    1. Execution Unit: Any registered, executable code (function, class, instance)
    2. Unit Type: Defines interface specification and how to execute
    3. Unit Spec: Metadata about a registered unit
    4. Unit Runner: Knows how to instantiate and execute units of a specific type
    5. Unified Registry: Single source of truth for all execution units

Architecture:
    ┌──────────────────────────────────────────────────────────────────┐
    │                    Unified Registry                              │
    │  {type: {name: UnitSpec}}                                        │
    │  - Type-safe storage                                             │
    │  - Discovery and introspection                                   │
    │  - Validation                                                    │
    └──────────────────────────────────────────────────────────────────┘
                            ▲          ▲
                            │          │
                 register() │          │ get()
                            │          │
    ┌───────────────────────┴──────────┴───────────────────────────────┐
    │                      Unit Types                                  │
    │                                                                   │
    │  Each type defines:                                              │
    │    - Interface protocol (what signature to implement)            │
    │    - Runner (how to execute)                                     │
    │    - Validator (type checking)                                   │
    └──────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
    ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
    │   Plugin     │ │   Renderer  │ │   Any New  │
    │   Type       │ │   Type      │ │   Type     │
    ├──────────────┤ ├─────────────┤ ├────────────┤
    │ Interface:   │ │ Interface:  │ │ Interface: │
    │ func(ctx)    │ │ .render()   │ │ Custom     │
    │              │ │             │ │            │
    │ Runner:      │ │ Runner:     │ │ Runner:    │
    │ Call func    │ │ Call render │ │ Custom     │
    └──────────────┘ └─────────────┘ └────────────┘

Example Usage:

    # Define a plugin type unit
    @register_unit("csv_loader", unit_type="plugin")
    def load_csv(ctx: PluginContext) -> pd.DataFrame:
        return pd.read_csv(ctx.config.file_path)

    # Define a renderer type unit
    @register_unit("speed", unit_type="renderer")
    class SpeedRenderer(BaseDataRenderer):
        def render(self, frame, timestamp_ms):
            return frame

    # Execute them
    execute_unit("csv_loader", "plugin", ctx)
    execute_unit("speed", "renderer", frame, timestamp_ms, config={...})
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, Union

logger = logging.getLogger(__name__)


# ============================================================================
# Core Abstractions
# ============================================================================

@dataclass
class UnitSpec:
    """
    Specification for an execution unit.

    Contains all metadata needed to identify, validate, and execute
    a unit of any type.
    """

    name: str
    unit_type: str  # e.g., "plugin", "renderer", "validator"
    implementation: Union[Callable, Type, Any]  # The actual code
    config_model: Optional[Type] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Auto-extract description from docstring."""
        if not self.description and hasattr(self.implementation, "__doc__"):
            self.description = self.implementation.__doc__ or ""


class UnitRunner(ABC):
    """
    Abstract base class for execution unit runners.

    Each unit type has its own runner that knows:
    - How to validate the unit implementation
    - How to instantiate it (if needed)
    - How to execute it with the correct arguments
    - How to handle lifecycle (caching, cleanup)
    """

    @abstractmethod
    def validate(self, spec: UnitSpec) -> bool:
        """
        Validate that implementation conforms to type's interface.

        Args:
            spec: Unit specification to validate

        Returns:
            True if valid

        Raises:
            TypeError: If implementation doesn't match interface
        """
        raise NotImplementedError

    @abstractmethod
    def execute(self, spec: UnitSpec, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the unit with given arguments.

        Args:
            spec: Unit specification
            *args: Positional arguments for execution
            **kwargs: Keyword arguments for execution

        Returns:
            Execution result
        """
        raise NotImplementedError


@dataclass
class UnitType:
    """
    Defines a type of execution unit.

    Each type specifies:
    - Name and description
    - Interface protocol (via runner validation)
    - How to execute (via runner)
    - Optional default config model
    """

    name: str
    runner: UnitRunner
    description: str = ""
    default_config_model: Optional[Type] = None


# ============================================================================
# Unified Registry
# ============================================================================

class UnifiedRegistry:
    """
    Type-agnostic registry for all execution units.

    Provides:
    - Registration with type validation
    - Type-safe lookup
    - Discovery and introspection
    - Namespace isolation between types
    """

    def __init__(self):
        # Structure: {unit_type: {name: UnitSpec}}
        self._units: Dict[str, Dict[str, UnitSpec]] = {}
        # Structure: {unit_type: UnitType}
        self._types: Dict[str, UnitType] = {}

    def register_type(self, unit_type: UnitType) -> None:
        """
        Register a new unit type.

        Args:
            unit_type: Type specification

        Raises:
            ValueError: If type already registered
        """
        if unit_type.name in self._types:
            raise ValueError(f"Unit type '{unit_type.name}' already registered")

        self._types[unit_type.name] = unit_type
        self._units[unit_type.name] = {}
        logger.info(f"Registered unit type: {unit_type.name}")

    def register_unit(
        self,
        name: str,
        unit_type: str,
        implementation: Union[Callable, Type, Any],
        config_model: Optional[Type] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        override: bool = False,
    ) -> None:
        """
        Register an execution unit.

        Args:
            name: Unit name (unique within type)
            unit_type: Type of unit (must be registered)
            implementation: The actual code (function, class, or instance)
            config_model: Optional pydantic model for configuration
            description: Human-readable description
            metadata: Additional metadata
            override: Allow overriding existing registration

        Raises:
            ValueError: If type not registered or unit already exists
            TypeError: If implementation doesn't match type's interface
        """
        # Validate type exists
        if unit_type not in self._types:
            available = ", ".join(self._types.keys())
            raise ValueError(
                f"Unit type '{unit_type}' not registered. "
                f"Available types: {available}"
            )

        # Check for existing registration
        if name in self._units[unit_type] and not override:
            raise ValueError(
                f"Unit '{name}' already registered as '{unit_type}'. "
                f"Use override=True to replace."
            )

        # Create spec
        spec = UnitSpec(
            name=name,
            unit_type=unit_type,
            implementation=implementation,
            config_model=config_model or self._types[unit_type].default_config_model,
            description=description,
            metadata=metadata or {},
        )

        # Validate implementation
        runner = self._types[unit_type].runner
        try:
            runner.validate(spec)
        except TypeError as e:
            raise TypeError(
                f"Unit '{name}' doesn't match '{unit_type}' interface: {e}"
            ) from e

        # Register
        self._units[unit_type][name] = spec
        logger.debug(f"Registered {unit_type} unit: {name}")

    def get_unit(self, name: str, unit_type: str) -> UnitSpec:
        """
        Get unit specification.

        Args:
            name: Unit name
            unit_type: Unit type

        Returns:
            Unit specification

        Raises:
            KeyError: If unit not found
        """
        if unit_type not in self._units:
            raise ValueError(f"Unit type '{unit_type}' not registered")

        if name not in self._units[unit_type]:
            available = ", ".join(self._units[unit_type].keys())
            raise KeyError(
                f"Unit '{name}' not found in type '{unit_type}'. "
                f"Available: {available}"
            )

        return self._units[unit_type][name]

    def list_units(
        self,
        unit_type: Optional[str] = None
    ) -> Dict[str, UnitSpec]:
        """
        List registered units.

        Args:
            unit_type: Filter by type (None = all types)

        Returns:
            Dictionary of {name: UnitSpec}
        """
        if unit_type is None:
            # Return all units from all types
            result = {}
            for type_units in self._units.values():
                result.update(type_units)
            return result
        else:
            return self._units.get(unit_type, {}).copy()

    def list_types(self) -> Dict[str, UnitType]:
        """List all registered unit types."""
        return self._types.copy()

    def has_unit(self, name: str, unit_type: str) -> bool:
        """Check if unit is registered."""
        return name in self._units.get(unit_type, {})

    def execute_unit(
        self,
        name: str,
        unit_type: str,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Execute a unit by name and type.

        Args:
            name: Unit name
            unit_type: Unit type
            *args: Positional arguments for execution
            **kwargs: Keyword arguments for execution

        Returns:
            Execution result
        """
        spec = self.get_unit(name, unit_type)
        runner = self._types[unit_type].runner
        return runner.execute(spec, *args, **kwargs)


# Global registry instance
_registry = UnifiedRegistry()


# ============================================================================
# Public API
# ============================================================================

def register_type(
    name: str,
    runner: UnitRunner,
    description: str = "",
    default_config_model: Optional[Type] = None,
) -> None:
    """
    Register a new execution unit type.

    Args:
        name: Type name (e.g., "plugin", "renderer")
        runner: Runner instance for this type
        description: Type description
        default_config_model: Default config model for units of this type

    Example:
        >>> runner = PluginRunner()
        >>> register_type("plugin", runner, "Data processing plugins")
    """
    unit_type = UnitType(
        name=name,
        runner=runner,
        description=description,
        default_config_model=default_config_model,
    )
    _registry.register_type(unit_type)


def register_unit(
    name: str,
    unit_type: str,
    config_model: Optional[Type] = None,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    override: bool = False,
) -> Callable:
    """
    Decorator to register an execution unit.

    Args:
        name: Unit name
        unit_type: Type of unit
        config_model: Optional pydantic model
        description: Description
        metadata: Additional metadata
        override: Allow overriding

    Returns:
        Decorator function

    Example:
        >>> @register_unit("csv_loader", unit_type="plugin")
        >>> def load_csv(ctx: PluginContext) -> pd.DataFrame:
        ...     return pd.read_csv(ctx.config.file_path)
    """
    def decorator(implementation: Union[Callable, Type]) -> Union[Callable, Type]:
        _registry.register_unit(
            name=name,
            unit_type=unit_type,
            implementation=implementation,
            config_model=config_model,
            description=description,
            metadata=metadata,
            override=override,
        )
        return implementation

    return decorator


def get_unit(name: str, unit_type: str) -> UnitSpec:
    """Get unit specification."""
    return _registry.get_unit(name, unit_type)


def list_units(unit_type: Optional[str] = None) -> Dict[str, UnitSpec]:
    """List registered units."""
    return _registry.list_units(unit_type)


def list_types() -> Dict[str, UnitType]:
    """List all registered unit types."""
    return _registry.list_types()


def execute_unit(
    name: str,
    unit_type: str,
    *args: Any,
    **kwargs: Any
) -> Any:
    """
    Execute a unit by name and type.

    Example:
        >>> execute_unit("csv_loader", "plugin", ctx)
        >>> execute_unit("speed", "renderer", frame, timestamp_ms, config={...})
    """
    return _registry.execute_unit(name, unit_type, *args, **kwargs)
