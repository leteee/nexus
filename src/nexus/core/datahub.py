"""
Central data hub for managing data lifecycle.

Following data_replay's DataHub pattern with lazy loading,
caching, and type-safe data access.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .handlers import get_handler, get_handler_for_path, preflight_type_check

logger = logging.getLogger(__name__)


class DataSource:
    """Configuration for a data source."""

    def __init__(
        self,
        path: Path,
        handler_type: str,
        must_exist: bool = True,
        expected_type: Optional[type] = None,
        handler_args: Optional[Dict[str, Any]] = None,
    ):
        self.path = path
        self.handler_type = handler_type
        self.must_exist = must_exist
        self.expected_type = expected_type
        self.handler_args = handler_args or {}


class DataHub:
    """
    Central hub for data management with lazy loading and caching.

    Manages the complete data lifecycle:
    - Registration of data sources
    - Lazy loading with caching
    - Type checking and validation
    - Save operations for outputs
    """

    def __init__(self, case_path: Path, logger: Optional[logging.Logger] = None):
        self.case_path = case_path
        self.logger = logger or logging.getLogger(__name__)
        self._data_cache: Dict[str, Any] = {}
        self._data_sources: Dict[str, DataSource] = {}

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
        Register a data source.

        Args:
            name: Unique name for the data source
            path: File path (relative to case_path or absolute)
            handler_type: Type of data handler to use
            must_exist: Whether the file must exist for loading
            expected_type: Expected data type for validation
            **handler_args: Additional arguments for the handler
        """
        # Resolve path relative to case directory
        resolved_path = Path(path)
        if not resolved_path.is_absolute():
            resolved_path = self.case_path / resolved_path

        data_source = DataSource(
            path=resolved_path,
            handler_type=handler_type,
            must_exist=must_exist,
            expected_type=expected_type,
            handler_args=handler_args,
        )

        self._data_sources[name] = data_source
        self.logger.debug(f"Registered data source '{name}' -> {resolved_path}")

        # Perform type check if possible
        if expected_type:
            try:
                handler = get_handler(handler_type)
                preflight_type_check(name, expected_type, handler)
            except Exception as e:
                self.logger.warning(f"Could not perform type check for '{name}': {e}")

    def get(self, name: str) -> Any:
        """
        Get data by name with lazy loading and caching.

        Args:
            name: Name of the data source

        Returns:
            Loaded data

        Raises:
            KeyError: If data source not registered
            FileNotFoundError: If required file doesn't exist
        """
        # Return cached data if available
        if name in self._data_cache:
            self.logger.debug(f"Returning cached data '{name}'")
            return self._data_cache[name]

        # Check if source is registered
        if name not in self._data_sources:
            raise KeyError(f"Data source '{name}' not registered")

        source = self._data_sources[name]

        # Check file existence
        if source.must_exist and not source.path.exists():
            raise FileNotFoundError(f"Required file not found: {source.path}")

        if not source.path.exists():
            self.logger.warning(f"Optional file not found: {source.path}")
            return None

        # Load and cache data
        self.logger.info(f"Loading data '{name}' from {source.path}")
        try:
            handler = get_handler(source.handler_type)
            data = handler.load(source.path)

            # Validate type if specified
            if source.expected_type and not isinstance(data, source.expected_type):
                self.logger.warning(
                    f"Type mismatch for '{name}': "
                    f"expected {source.expected_type.__name__}, "
                    f"got {type(data).__name__}"
                )

            self._data_cache[name] = data
            return data

        except Exception as e:
            self.logger.error(f"Failed to load data '{name}': {e}")
            raise

    def save(
        self,
        name: str,
        data: Any,
        path: Optional[str] = None,
        handler_type: Optional[str] = None,
    ) -> None:
        """
        Save data to the specified path.

        Args:
            name: Name for the data (for caching and logging)
            data: Data to save
            path: Path to save to (uses registered path if not provided)
            handler_type: Handler type (auto-detected if not provided)
        """
        # Use registered source if path not provided
        if path is None:
            if name not in self._data_sources:
                raise KeyError(f"No registered path for data '{name}'")
            target_path = self._data_sources[name].path
            target_handler_type = self._data_sources[name].handler_type
        else:
            target_path = Path(path)
            if not target_path.is_absolute():
                target_path = self.case_path / target_path
            target_handler_type = handler_type

        # Auto-detect handler type if not provided
        if target_handler_type is None:
            try:
                handler = get_handler_for_path(target_path)
                target_handler_type = target_path.suffix.lstrip(".")
            except ValueError:
                raise ValueError(f"Cannot determine handler type for {target_path}")
        else:
            handler = get_handler(target_handler_type)

        self.logger.info(f"Saving data '{name}' to {target_path}")
        try:
            handler.save(data, target_path)
            # Cache the saved data
            self._data_cache[name] = data

        except Exception as e:
            self.logger.error(f"Failed to save data '{name}': {e}")
            raise

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

        if name not in self._data_sources:
            return False

        return self._data_sources[name].path.exists()

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
            self.logger.debug(f"Cleared cached data '{name}'")

    def list_sources(self) -> Dict[str, str]:
        """
        List all registered data sources.

        Returns:
            Dictionary mapping source names to their paths
        """
        return {name: str(source.path) for name, source in self._data_sources.items()}

    def get_cached_data(self) -> Dict[str, Any]:
        """
        Get all currently cached data.

        Returns:
            Dictionary of cached data
        """
        return self._data_cache.copy()