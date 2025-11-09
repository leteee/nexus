"""
Path resolution utilities for automatic path handling in plugin configurations.

Convention:
    Any parameter named '*_path' will be automatically resolved to an absolute path
    relative to the case directory.

Examples:
    data_path: "input/data.json"           -> /abs/case/path/input/data.json
    calibration_path: "calib.yaml"         -> /abs/case/path/calib.yaml
    output_dir: "output"                   -> "output" (not resolved)

To disable auto-resolution for a specific field:
    Use Field(..., json_schema_extra={"skip_path_resolve": True})
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from pydantic import BaseModel


class PathResolver:
    """
    Automatic path resolution for plugin configurations.

    Resolves all parameters ending with '_path' to absolute paths relative to
    the case directory. Supports nested dictionaries, lists, and Pydantic models.

    Thread-safe and suitable for use in concurrent environments.
    """

    # Convention marker in parameter names
    PATH_SUFFIX = "_path"

    @staticmethod
    def should_resolve_field(field_name: str, field_info: Any = None) -> bool:
        """
        Determine if a field should be auto-resolved.

        Args:
            field_name: Name of the field
            field_info: Optional Pydantic FieldInfo for metadata checking

        Returns:
            True if field should be resolved
        """
        # Check if field name follows convention
        if not field_name.endswith(PathResolver.PATH_SUFFIX):
            return False

        # Check if explicitly disabled via Field metadata
        if field_info and hasattr(field_info, 'json_schema_extra'):
            extra = field_info.json_schema_extra or {}
            if extra.get('skip_path_resolve', False):
                return False

        return True

    @staticmethod
    def resolve_value(
        value: Any,
        resolve_fn: Callable[[Union[str, Path]], Path],
    ) -> Any:
        """
        Resolve a single value (may be string, dict, list, or None).

        Args:
            value: Value to resolve
            resolve_fn: Function to resolve paths (e.g., ctx.resolve_path)

        Returns:
            Resolved value
        """
        if value is None:
            return None

        if isinstance(value, (str, Path)):
            return resolve_fn(value)

        if isinstance(value, dict):
            return PathResolver.resolve_dict(value, resolve_fn)

        if isinstance(value, list):
            return PathResolver.resolve_list(value, resolve_fn)

        # Other types pass through unchanged
        return value

    @staticmethod
    def resolve_dict(
        params: Dict[str, Any],
        resolve_fn: Callable[[Union[str, Path]], Path],
        skip_keys: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Recursively resolve all '*_path' parameters in a dictionary.

        Args:
            params: Dictionary of parameters
            resolve_fn: Function to resolve paths
            skip_keys: Optional set of keys to skip resolution

        Returns:
            Dictionary with all path parameters resolved

        Example:
            >>> params = {
            ...     "data_path": "input/data.json",
            ...     "config": {
            ...         "calibration_path": "calib.yaml"
            ...     },
            ...     "threshold": 0.5
            ... }
            >>> resolved = PathResolver.resolve_dict(params, ctx.resolve_path)
            >>> # All *_path fields are now absolute paths
        """
        skip_keys = skip_keys or set()
        resolved = {}

        for key, value in params.items():
            # Skip explicitly excluded keys
            if key in skip_keys:
                resolved[key] = value
                continue

            # Resolve path fields
            if key.endswith(PathResolver.PATH_SUFFIX):
                resolved[key] = PathResolver.resolve_value(value, resolve_fn)
            # Recursively handle nested structures
            elif isinstance(value, dict):
                resolved[key] = PathResolver.resolve_dict(value, resolve_fn, skip_keys)
            elif isinstance(value, list):
                resolved[key] = PathResolver.resolve_list(value, resolve_fn, skip_keys)
            else:
                resolved[key] = value

        return resolved

    @staticmethod
    def resolve_list(
        items: List[Any],
        resolve_fn: Callable[[Union[str, Path]], Path],
        skip_keys: Optional[Set[str]] = None,
    ) -> List[Any]:
        """
        Recursively resolve path parameters in a list of items.

        Args:
            items: List of items (may contain dicts)
            resolve_fn: Function to resolve paths
            skip_keys: Optional set of keys to skip in nested dicts

        Returns:
            List with path parameters resolved
        """
        resolved = []
        for item in items:
            if isinstance(item, dict):
                resolved.append(PathResolver.resolve_dict(item, resolve_fn, skip_keys))
            elif isinstance(item, list):
                resolved.append(PathResolver.resolve_list(item, resolve_fn, skip_keys))
            else:
                resolved.append(item)
        return resolved

    @staticmethod
    def resolve_config(
        config: BaseModel,
        resolve_fn: Callable[[Union[str, Path]], Path],
    ) -> None:
        """
        Resolve path fields in a Pydantic model in-place.

        Automatically detects fields ending with '_path' and resolves them.
        Respects Field metadata 'skip_path_resolve' flag.

        Args:
            config: Pydantic model instance
            resolve_fn: Function to resolve paths

        Example:
            >>> class MyConfig(PluginConfig):
            ...     data_path: str = "input/data.json"
            ...     output_path: str = "output/results.csv"
            ...     threshold: float = 0.5
            >>>
            >>> config = MyConfig()
            >>> PathResolver.resolve_config(config, ctx.resolve_path)
            >>> # data_path and output_path are now absolute paths
        """
        # Iterate over all fields in the model
        for field_name, field_info in config.model_fields.items():
            # Check if should resolve
            if not PathResolver.should_resolve_field(field_name, field_info):
                continue

            # Get current value
            value = getattr(config, field_name, None)
            if value is None:
                continue

            # Resolve and set back
            resolved_value = PathResolver.resolve_value(value, resolve_fn)
            setattr(config, field_name, resolved_value)


def auto_resolve_paths(
    config: Union[Dict[str, Any], BaseModel],
    resolve_fn: Callable[[Union[str, Path]], Path],
    skip_keys: Optional[Set[str]] = None,
) -> Union[Dict[str, Any], BaseModel]:
    """
    Automatically resolve all path parameters in configuration.

    Convenience function that handles both dict and Pydantic configs.

    Args:
        config: Configuration (dict or Pydantic model)
        resolve_fn: Function to resolve paths (e.g., ctx.resolve_path)
        skip_keys: Optional set of keys to skip

    Returns:
        Configuration with paths resolved

    Example:
        >>> # With dict
        >>> config = {"data_path": "input/data.json", "threshold": 0.5}
        >>> resolved = auto_resolve_paths(config, ctx.resolve_path)
        >>>
        >>> # With Pydantic model
        >>> config = MyConfig(data_path="input/data.json")
        >>> auto_resolve_paths(config, ctx.resolve_path)
    """
    if isinstance(config, BaseModel):
        PathResolver.resolve_config(config, resolve_fn)
        return config
    elif isinstance(config, dict):
        return PathResolver.resolve_dict(config, resolve_fn, skip_keys)
    else:
        raise TypeError(f"Unsupported config type: {type(config)}")
