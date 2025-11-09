"""
Configuration reference resolver for Nexus framework.

Supports referencing shared configurations using @defaults namespace:
    - Direct reference: value: "@defaults.xxx"
    - Extend and override: _extends: "@defaults.xxx" + local fields

Best Practices:
    - All shared configs go in 'defaults' namespace
    - Use @prefix for references
    - Use _extends for inheritance
    - Deep merge on conflicts
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Union

# Configuration reference pattern: @defaults.path.to.config
REFERENCE_PATTERN = re.compile(r'^@([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)$')

# Reserved key for extending configurations
EXTENDS_KEY = '_extends'

# Default namespace for shared configurations
DEFAULT_NAMESPACE = 'defaults'


class ConfigResolutionError(Exception):
    """Raised when configuration reference cannot be resolved."""
    pass


class ConfigResolver:
    """
    Resolve configuration references and merge configurations.

    Features:
        - Reference syntax: @defaults.path.to.config
        - Extends syntax: _extends: @defaults.xxx
        - Deep merge for nested dicts
        - Circular reference detection
    """

    def __init__(self, defaults: Dict[str, Any]):
        """
        Initialize resolver with defaults namespace.

        Args:
            defaults: Shared configuration dictionary from 'defaults' key

        Example:
            >>> defaults = {
            ...     'speed_renderer': {
            ...         'position': [30, 60],
            ...         'tolerance_ms': 5000.0
            ...     }
            ... }
            >>> resolver = ConfigResolver(defaults)
        """
        self.defaults = defaults or {}
        self._resolution_stack: List[str] = []

    def resolve(self, config: Any) -> Any:
        """
        Resolve all references in configuration.

        Args:
            config: Configuration value (dict, list, str, etc.)

        Returns:
            Resolved configuration with all references expanded

        Raises:
            ConfigResolutionError: If reference cannot be resolved

        Example:
            >>> config = {'kwargs': '@defaults.speed_renderer'}
            >>> resolved = resolver.resolve(config)
            >>> # resolved['kwargs'] contains the actual config
        """
        return self._resolve_value(config)

    def _resolve_value(self, value: Any) -> Any:
        """Resolve a single value (may be reference, dict, list, or primitive)."""
        if isinstance(value, str):
            return self._resolve_reference(value)
        elif isinstance(value, dict):
            return self._resolve_dict(value)
        elif isinstance(value, list):
            return self._resolve_list(value)
        else:
            # Primitives pass through unchanged
            return value

    def _resolve_reference(self, value: str) -> Any:
        """
        Resolve a reference string like '@defaults.speed_renderer'.

        Args:
            value: String that may be a reference

        Returns:
            Referenced value or original string if not a reference
        """
        match = REFERENCE_PATTERN.match(value)
        if not match:
            # Not a reference, return as-is
            return value

        ref_path = match.group(1)

        # Check for circular references
        if ref_path in self._resolution_stack:
            chain = ' -> '.join(self._resolution_stack + [ref_path])
            raise ConfigResolutionError(
                f"Circular reference detected: {chain}"
            )

        # Parse path: defaults.speed_renderer -> ['speed_renderer']
        parts = ref_path.split('.')

        if parts[0] != DEFAULT_NAMESPACE:
            raise ConfigResolutionError(
                f"Invalid reference '{value}': must start with '@{DEFAULT_NAMESPACE}.'"
            )

        # Navigate to referenced value
        self._resolution_stack.append(ref_path)
        try:
            current = self.defaults
            path_parts = parts[1:]  # Skip 'defaults' namespace

            for part in path_parts:
                if not isinstance(current, dict) or part not in current:
                    raise ConfigResolutionError(
                        f"Reference '{value}' not found: '{part}' missing in path"
                    )
                current = current[part]

            # Recursively resolve the referenced value
            resolved = self._resolve_value(deepcopy(current))
            return resolved

        finally:
            self._resolution_stack.pop()

    def _resolve_dict(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve a dictionary configuration.

        Handles two cases:
        1. Contains _extends: inherit and merge
        2. Normal dict: recursively resolve all values
        """
        if EXTENDS_KEY in config:
            return self._resolve_extends(config)

        # Normal dict: resolve all values
        resolved = {}
        for key, value in config.items():
            resolved[key] = self._resolve_value(value)
        return resolved

    def _resolve_extends(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve _extends configuration.

        Merges base configuration with local overrides.

        Example:
            >>> config = {
            ...     '_extends': '@defaults.speed_renderer',
            ...     'data_path': 'input/speed.jsonl',
            ...     'color': [255, 0, 0]
            ... }
            >>> # Result: base config + local fields (local overrides base)
        """
        extends_ref = config[EXTENDS_KEY]

        if not isinstance(extends_ref, str):
            raise ConfigResolutionError(
                f"'{EXTENDS_KEY}' must be a string reference, got {type(extends_ref)}"
            )

        # Resolve the base configuration
        base_config = self._resolve_reference(extends_ref)

        if not isinstance(base_config, dict):
            raise ConfigResolutionError(
                f"Cannot extend non-dict value: {extends_ref} -> {type(base_config)}"
            )

        # Create local config without _extends key
        local_config = {k: v for k, v in config.items() if k != EXTENDS_KEY}

        # Deep merge: base + local (local overrides base)
        merged = self._deep_merge(base_config, local_config)

        # Resolve the merged result
        return self._resolve_dict(merged)

    def _resolve_list(self, items: List[Any]) -> List[Any]:
        """Resolve all items in a list."""
        return [self._resolve_value(item) for item in items]

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base configuration
            override: Override configuration (takes precedence)

        Returns:
            Merged dictionary (base + override)

        Rules:
            - Override keys replace base keys
            - For nested dicts, recursively merge
            - Lists are replaced, not merged
        """
        result = deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Both are dicts: deep merge
                result[key] = ConfigResolver._deep_merge(result[key], value)
            else:
                # Override or new key: replace
                result[key] = deepcopy(value)

        return result


def resolve_config(
    config: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Resolve all configuration references.

    Convenience function for resolving configurations.

    Args:
        config: Configuration to resolve
        defaults: Shared defaults namespace

    Returns:
        Resolved configuration

    Example:
        >>> defaults = {'speed_renderer': {'position': [30, 60]}}
        >>> config = {'kwargs': '@defaults.speed_renderer'}
        >>> resolved = resolve_config(config, defaults)
        >>> resolved['kwargs']['position']  # [30, 60]
    """
    resolver = ConfigResolver(defaults)
    return resolver.resolve(config)
