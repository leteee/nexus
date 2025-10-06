"""
Central data hub for managing data lifecycle with hybrid path resolution.

Supports three path resolution strategies:
1. Explicit logical names: @customer_master
2. Implicit logical names: customer_master (if exists in data_sources)
3. Direct paths: data/file.csv
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DataHub:
    """
    Central hub for data management with hybrid path resolution strategy.

    Manages the complete data lifecycle:
    - Registration of global data sources (from case.yaml data_sources)
    - Smart path resolution (logical names vs direct paths)
    - Lazy loading with caching
    - Type checking and validation
    - Save operations for outputs
    """

    # Explicit logical name prefix
    LOGICAL_NAME_PREFIX = "@"

    # Valid logical name pattern (identifier format)
    IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(self, case_path: Path, logger: Optional[logging.Logger] = None):
        self.case_path = case_path
        self.logger = logger or logging.getLogger(__name__)
        self._data_cache: Dict[str, Any] = {}
        self._data_sources: Dict[str, Dict] = {}  # Global data sources from case.yaml
        self._registered_sources: Dict[str, Dict] = {}  # Runtime registered sources

    # ==================== Global Data Source Management ====================

    def register_global_sources(self, data_sources: Dict[str, Dict]):
        """
        Register global data sources from case.yaml data_sources section.

        Validates naming conventions and warns about non-standard names.

        Args:
            data_sources: Dictionary of data source configurations
        """
        for name, config in data_sources.items():
            if not self._is_valid_logical_name_format(name):
                self.logger.warning(
                    f"Data source name '{name}' does not follow identifier convention.\n"
                    f"  Recommended format: customer_master, product_v2, staging_data\n"
                    f"  This name contains special characters and must be referenced with '@{name}'"
                )

            self._data_sources[name] = config

        self.logger.info(f"Registered {len(data_sources)} global data sources")

    def _is_valid_logical_name_format(self, name: str) -> bool:
        """Check if name follows identifier naming convention."""
        return bool(self.IDENTIFIER_PATTERN.match(name))

    # ==================== Hybrid Path Resolution ====================

    def resolve_path(self, value: str) -> str:
        """
        Smart path resolution using hybrid strategy.

        Resolution order:
        1. @logical_name → Explicit logical name (must exist in data_sources)
        2. identifier    → Implicit logical name (if exists in data_sources)
        3. path/to/file  → Direct path

        Args:
            value: Configuration value (logical name or path)

        Returns:
            Resolved physical path

        Raises:
            ValueError: If explicit logical name (@name) is not defined
        """
        # Strategy 1: Explicit logical name (@ prefix)
        if value.startswith(self.LOGICAL_NAME_PREFIX):
            return self._resolve_explicit_logical_name(value)

        # Strategy 2: Implicit logical name (identifier format + exists)
        if self._is_valid_logical_name_format(value):
            if value in self._data_sources:
                return self._resolve_implicit_logical_name(value)

        # Strategy 3: Direct path
        return self._resolve_direct_path(value)

    def _resolve_explicit_logical_name(self, value: str) -> str:
        """Resolve explicit logical name (@prefix)."""
        logical_name = value[len(self.LOGICAL_NAME_PREFIX) :]

        if logical_name not in self._data_sources:
            available = ", ".join(self._data_sources.keys())
            raise ValueError(
                f"Logical name '{value}' is not defined in data_sources.\n"
                f"  Available logical names: {available or '(none)'}"
            )

        path = self._data_sources[logical_name]["path"]
        self.logger.debug(f"Resolved explicit logical name: {value} → {path}")
        return path

    def _resolve_implicit_logical_name(self, value: str) -> str:
        """Resolve implicit logical name (auto-detected)."""
        path = self._data_sources[value]["path"]
        self.logger.debug(f"Resolved implicit logical name: {value} → {path}")
        return path

    def _resolve_direct_path(self, value: str) -> str:
        """Resolve direct path."""
        self.logger.debug(f"Resolved direct path: {value}")
        return value

    # ==================== Handler Resolution ====================

    def resolve_handler(self, value: str, default_handler: str) -> str:
        """
        Smart handler resolution.

        Args:
            value: Configuration value (logical name or path)
            default_handler: Default handler type to use

        Returns:
            Resolved handler type
        """
        # Explicit logical name
        if value.startswith(self.LOGICAL_NAME_PREFIX):
            logical_name = value[len(self.LOGICAL_NAME_PREFIX) :]
            if logical_name in self._data_sources:
                return self._data_sources[logical_name].get("handler", default_handler)

        # Implicit logical name
        if self._is_valid_logical_name_format(value):
            if value in self._data_sources:
                return self._data_sources[value].get("handler", default_handler)

        # Direct path - use default handler
        return default_handler

    def resolve_handler_args(self, value: str) -> Dict[str, Any]:
        """
        Resolve additional handler arguments from data sources.

        Args:
            value: Configuration value (logical name or path)

        Returns:
            Handler arguments (excluding 'path' and 'handler' keys)
        """
        # Explicit logical name
        if value.startswith(self.LOGICAL_NAME_PREFIX):
            logical_name = value[len(self.LOGICAL_NAME_PREFIX) :]
            if logical_name in self._data_sources:
                config = self._data_sources[logical_name]
                return {k: v for k, v in config.items() if k not in ["path", "handler"]}

        # Implicit logical name
        if self._is_valid_logical_name_format(value):
            if value in self._data_sources:
                config = self._data_sources[value]
                return {k: v for k, v in config.items() if k not in ["path", "handler"]}

        return {}

    # ==================== Runtime Data Source Registration ====================

    def register_source(
        self,
        name: str,
        path: str,
        handler_type: str,
        must_exist: bool = True,
        expected_type: Optional[type] = None,
        **handler_args,
    ) -> None:
        """
        Register a data source for runtime use.

        Called by the engine before plugin execution to register DataSource fields.

        Args:
            name: Field name from plugin config
            path: Path value (already resolved by resolve_path)
            handler_type: Handler type (already resolved by resolve_handler)
            must_exist: Whether file must exist for loading
            expected_type: Expected data type for validation
            **handler_args: Additional handler arguments
        """
        # Resolve physical path
        resolved_path = Path(path)
        if not resolved_path.is_absolute():
            resolved_path = self.case_path / resolved_path

        # Store configuration
        self._registered_sources[name] = {
            "path": resolved_path,
            "handler_type": handler_type,
            "must_exist": must_exist,
            "expected_type": expected_type,
            "handler_args": handler_args,
        }

        self.logger.debug(f"Registered data source: {name} → {resolved_path}")

    # ==================== Data Access ====================

    def get(self, name: str) -> Any:
        """
        Load data by name with lazy loading and caching.

        Args:
            name: Name of the data source

        Returns:
            Loaded data

        Raises:
            KeyError: If data source not registered
            FileNotFoundError: If required file doesn't exist
        """
        from .handlers import get_handler

        # Return cached data if available
        if name in self._data_cache:
            self.logger.debug(f"Returning cached data: {name}")
            return self._data_cache[name]

        # Check if source is registered
        if name not in self._registered_sources:
            raise KeyError(f"Data source '{name}' not registered in DataHub")

        source = self._registered_sources[name]

        # Check file existence
        if source["must_exist"] and not source["path"].exists():
            raise FileNotFoundError(f"Required file not found: {source['path']}")

        if not source["path"].exists():
            self.logger.warning(f"Optional file not found: {source['path']}")
            return None

        # Load and cache data
        self.logger.info(f"Loading data: {name} <- {source['path']}")
        handler = get_handler(source["handler_type"])
        data = handler.load(source["path"])

        # Validate type if specified
        if source["expected_type"] and not isinstance(data, source["expected_type"]):
            self.logger.warning(
                f"Type mismatch for '{name}': "
                f"expected {source['expected_type'].__name__}, "
                f"got {type(data).__name__}"
            )

        # Cache the data
        self._data_cache[name] = data
        return data

    def save(
        self,
        name: str,
        data: Any,
        path: str,
        handler_type: str,
    ) -> None:
        """
        Save data to the specified path.

        Args:
            name: Name for the data (for caching and logging)
            data: Data to save
            path: Path to save to (already resolved)
            handler_type: Handler type (already resolved)
        """
        from .handlers import get_handler

        # Resolve physical path
        target_path = Path(path)
        if not target_path.is_absolute():
            target_path = self.case_path / target_path

        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Save data
        self.logger.info(f"Saving data: {name} → {target_path}")
        handler = get_handler(handler_type)
        handler.save(data, target_path)

        # Cache the saved data
        self._data_cache[name] = data

    # ==================== Utility Methods ====================

    def exists(self, name: str) -> bool:
        """
        Check if data source exists (either cached or on disk).

        Args:
            name: Name of the data source

        Returns:
            True if data exists, False otherwise
        """
        if name in self._data_cache:
            return True

        if name not in self._registered_sources:
            return False

        return self._registered_sources[name]["path"].exists()

    def clear_cache(self, name: Optional[str] = None) -> None:
        """
        Clear cached data.

        Args:
            name: Specific data to clear, or None to clear all
        """
        if name is None:
            self._data_cache.clear()
            self.logger.debug("Cleared entire data cache")
        elif name in self._data_cache:
            del self._data_cache[name]
            self.logger.debug(f"Cleared cached data: {name}")

    def list_global_sources(self) -> Dict[str, str]:
        """
        List all global data sources.

        Returns:
            Dictionary mapping logical names to their paths
        """
        return {
            name: config.get("path", "") for name, config in self._data_sources.items()
        }

    def list_registered_sources(self) -> Dict[str, str]:
        """
        List all runtime registered data sources.

        Returns:
            Dictionary mapping source names to their paths
        """
        return {
            name: str(config["path"])
            for name, config in self._registered_sources.items()
        }

    def get_cached_data(self) -> Dict[str, Any]:
        """
        Get all currently cached data.

        Returns:
            Dictionary of cached data
        """
        return self._data_cache.copy()
