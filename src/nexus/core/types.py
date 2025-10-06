"""
Core type definitions and annotations for the Nexus framework.

Following data_replay's approach of clear type definitions with
functional programming principles.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from pydantic import BaseModel


class DataSource:
    """
    Annotation for data input dependencies in plugin configurations.

    Used with Annotated types to declare data source requirements:

    Example:
        class MyConfig(PluginConfig):
            input_data: Annotated[str, DataSource(
                handler="csv",
                required=True,
                schema=pd.DataFrame
            )] = "data/input.csv"

    The framework automatically:
    - Registers the data source in DataHub
    - Loads data when plugin executes
    - Validates data type if schema is specified
    """

    def __init__(
        self,
        handler: str = "csv",
        required: bool = True,
        schema: Optional[type] = None,
        handler_args: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            handler: Data handler type (csv, parquet, json, etc.)
            required: Whether the data source must exist
            schema: Expected data type for validation
            handler_args: Additional arguments for the handler
        """
        self.handler = handler
        self.required = required
        self.schema = schema
        self.handler_args = handler_args or {}


class DataSink:
    """
    Annotation for data output destinations in plugin configurations.

    Used with Annotated types to declare where plugin outputs should be saved:

    Example:
        class MyConfig(PluginConfig):
            output_data: Annotated[str, DataSink(
                handler="parquet"
            )] = "data/output.parquet"

    The framework automatically:
    - Saves plugin return value to the specified path
    - Uses the specified handler for serialization
    - Creates parent directories if needed
    """

    def __init__(
        self,
        handler: str = "csv",
        schema: Optional[type] = None,
        handler_args: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            handler: Data handler type (csv, parquet, json, etc.)
            schema: Expected output data type
            handler_args: Additional arguments for the handler
        """
        self.handler = handler
        self.schema = schema
        self.handler_args = handler_args or {}


class PluginConfig(BaseModel):
    """
    Base class for plugin configuration models.

    All plugin configurations inherit from this to ensure
    proper validation and type safety.

    DataSource and DataSink fields should be declared using Annotated:

    Example:
        class DataCleanerConfig(PluginConfig):
            # I/O configuration
            input_data: Annotated[str, DataSource(handler="csv")] = "data/raw.csv"
            output_data: Annotated[str, DataSink(handler="parquet")] = "data/clean.parquet"

            # Behavior configuration
            remove_nulls: bool = True
            fill_strategy: str = "mean"
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}


@runtime_checkable
class DataHandler(Protocol):
    """
    Protocol for data handlers.

    Defines the interface that all data handlers must implement.
    Following data_replay's handler pattern.
    """

    def load(self, path: Path) -> Any:
        """Load data from the specified path."""
        ...

    def save(self, data: Any, path: Path) -> None:
        """Save data to the specified path."""
        ...

    @property
    def produced_type(self) -> type:
        """Return the type of data this handler produces."""
        ...


class PluginSpec:
    """
    Specification for a registered plugin.

    Contains all metadata needed to execute a plugin,
    following data_replay's plugin specification pattern.
    """

    def __init__(
        self,
        name: str,
        func: callable,
        config_model: Optional[type[PluginConfig]] = None,
        description: Optional[str] = None,
    ):
        self.name = name
        self.func = func
        self.config_model = config_model
        self.description = description or func.__doc__
