"""
Concrete runner implementations for standard execution unit types.

Provides ready-to-use runners for:
- Plugin type: func(ctx: PluginContext) -> Any
- Renderer type: class.render(frame, timestamp_ms) -> frame

These runners can be used as references for implementing new unit types.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Optional

from .execution_units import UnitRunner, UnitSpec

logger = logging.getLogger(__name__)


# ============================================================================
# Plugin Type Runner
# ============================================================================

class PluginRunner(UnitRunner):
    """
    Runner for plugin-type execution units.

    Interface specification:
        func(ctx: PluginContext) -> Any

    Where:
        - func: A callable function
        - ctx: PluginContext object with config, paths, shared_state
        - Returns: Any result

    Validation:
        - Must be callable
        - Must accept at least one positional argument

    Execution:
        - Calls function directly with provided context
        - No caching or state management

    Example:
        >>> @register_unit("csv_loader", unit_type="plugin")
        >>> def load_csv(ctx: PluginContext) -> pd.DataFrame:
        ...     return pd.read_csv(ctx.config.file_path)
    """

    def validate(self, spec: UnitSpec) -> bool:
        """
        Validate plugin interface.

        Args:
            spec: Unit specification

        Returns:
            True if valid

        Raises:
            TypeError: If not callable or wrong signature
        """
        impl = spec.implementation

        # Must be callable
        if not callable(impl):
            raise TypeError(
                f"Plugin '{spec.name}' must be callable, got {type(impl)}"
            )

        # Check signature (must accept at least one argument)
        try:
            sig = inspect.signature(impl)
            if len(sig.parameters) < 1:
                raise TypeError(
                    f"Plugin '{spec.name}' must accept at least one argument (ctx)"
                )
        except (ValueError, TypeError):
            # Can't inspect signature (e.g., built-in), assume it's OK
            pass

        return True

    def execute(self, spec: UnitSpec, ctx: Any) -> Any:
        """
        Execute plugin with context.

        Args:
            spec: Unit specification
            ctx: PluginContext object

        Returns:
            Plugin execution result
        """
        func = spec.implementation
        logger.debug(f"Executing plugin: {spec.name}")

        try:
            result = func(ctx)
            logger.debug(f"Plugin '{spec.name}' completed successfully")
            return result
        except Exception as e:
            logger.error(f"Plugin '{spec.name}' failed: {e}")
            raise


# ============================================================================
# Renderer Type Runner
# ============================================================================

class RendererRunner(UnitRunner):
    """
    Runner for renderer-type execution units.

    Interface specification:
        class implementing:
            def __init__(self, **config): ...
            def render(self, frame, timestamp_ms: int) -> frame: ...

    Where:
        - class: A class (not instance) implementing render() method
        - config: Configuration dict passed to __init__
        - frame: Video frame (numpy array)
        - timestamp_ms: Frame timestamp in milliseconds
        - Returns: Modified frame

    Validation:
        - Must be a class or have render() method
        - render() must accept at least 2 arguments (self, frame, timestamp_ms)

    Execution:
        - Creates instance on first call (with config)
        - Caches instance for subsequent calls
        - Calls render() method with frame and timestamp

    Lifecycle:
        - Instances are cached per unit name
        - Call clear_cache() to force re-instantiation

    Example:
        >>> @register_unit("speed", unit_type="renderer")
        >>> class SpeedRenderer(BaseDataRenderer):
        ...     def __init__(self, data_path, **kwargs):
        ...         super().__init__(data_path, **kwargs)
        ...
        ...     def render(self, frame, timestamp_ms):
        ...         # Draw speed on frame
        ...         return frame
    """

    def __init__(self):
        # Cache instances: {unit_name: instance}
        self._instances: Dict[str, Any] = {}

    def validate(self, spec: UnitSpec) -> bool:
        """
        Validate renderer interface.

        Args:
            spec: Unit specification

        Returns:
            True if valid

        Raises:
            TypeError: If doesn't implement render() or wrong signature
        """
        impl = spec.implementation

        # Check if it's a class or already has render method
        if inspect.isclass(impl):
            # It's a class - check if it will have render() when instantiated
            if not hasattr(impl, "render"):
                raise TypeError(
                    f"Renderer class '{spec.name}' must define render() method"
                )
            render_method = impl.render
        else:
            # It's an instance or function - must have render attribute
            if not hasattr(impl, "render"):
                raise TypeError(
                    f"Renderer '{spec.name}' must have render() method"
                )
            render_method = impl.render

        # Validate render() signature
        if callable(render_method):
            try:
                sig = inspect.signature(render_method)
                params = list(sig.parameters.keys())

                # Should have at least: self/frame, timestamp_ms
                # (or frame, timestamp_ms if it's a static method/function)
                if len(params) < 2:
                    raise TypeError(
                        f"Renderer '{spec.name}' render() must accept "
                        f"at least 2 arguments (frame, timestamp_ms), "
                        f"got {len(params)}: {params}"
                    )
            except (ValueError, TypeError):
                # Can't inspect, assume OK
                pass

        return True

    def execute(
        self,
        spec: UnitSpec,
        frame: Any,
        timestamp_ms: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute renderer with frame and timestamp.

        Args:
            spec: Unit specification
            frame: Video frame
            timestamp_ms: Frame timestamp
            config: Configuration dict for instantiation (required for first call)

        Returns:
            Rendered frame

        Raises:
            ValueError: If config not provided for uninstantiated class
        """
        # Get or create instance
        if spec.name not in self._instances:
            impl = spec.implementation

            # Check if it's a class that needs instantiation
            if inspect.isclass(impl):
                if config is None:
                    raise ValueError(
                        f"Config required for renderer '{spec.name}' instantiation"
                    )
                logger.debug(f"Instantiating renderer: {spec.name}")
                instance = impl(**config)
            else:
                # Already an instance
                instance = impl

            self._instances[spec.name] = instance

        # Execute render
        renderer = self._instances[spec.name]
        logger.debug(f"Executing renderer: {spec.name}")

        try:
            result = renderer.render(frame, timestamp_ms)
            return result
        except Exception as e:
            logger.error(f"Renderer '{spec.name}' failed: {e}")
            raise

    def clear_cache(self, unit_name: Optional[str] = None) -> None:
        """
        Clear cached renderer instances.

        Args:
            unit_name: Specific unit to clear (None = clear all)
        """
        if unit_name is None:
            self._instances.clear()
            logger.debug("Cleared all renderer instances")
        else:
            self._instances.pop(unit_name, None)
            logger.debug(f"Cleared renderer instance: {unit_name}")

    def get_instance(self, unit_name: str) -> Optional[Any]:
        """
        Get cached renderer instance.

        Args:
            unit_name: Unit name

        Returns:
            Cached instance or None
        """
        return self._instances.get(unit_name)


# ============================================================================
# Auto-registration of standard types
# ============================================================================

def register_standard_types() -> None:
    """
    Register standard execution unit types.

    Registers:
    - plugin: For data processing functions
    - renderer: For frame rendering classes

    This function is called automatically when module is imported.
    """
    from .execution_units import register_type

    # Register plugin type
    register_type(
        name="plugin",
        runner=PluginRunner(),
        description="Data processing plugins: func(ctx: PluginContext) -> Any",
    )

    # Register renderer type
    register_type(
        name="renderer",
        runner=RendererRunner(),
        description="Frame renderers: class.render(frame, timestamp_ms) -> frame",
    )

    logger.info("Registered standard execution unit types: plugin, renderer")


# Auto-register on import
register_standard_types()
