"""Factory for creating data connectors.

This module provides a factory pattern for creating data connector instances,
similar to the LLMProvider factory. It supports:

1. Getting connectors by name
2. Registering new connector types at runtime
3. Listing available connectors
"""

import logging
from typing import Any, Dict, Optional, Type

from quration.config import get_config
from quration.data_sources.base import DataConnector

logger = logging.getLogger(__name__)


# Connector registry - populated during module imports
_CONNECTOR_REGISTRY: Dict[str, Type[DataConnector]] = {}


def register_connector(
    name: str, connector_class: Type[DataConnector], override: bool = False
) -> None:
    """Register a new connector type.

    This allows plugins/extensions to add new connectors at runtime.
    Also used internally to register built-in connectors.

    Args:
        name: Connector name (e.g., 'geo', 'ena', 'pdb')
        connector_class: Connector class (must inherit from DataConnector)
        override: If True, allow overriding existing connectors

    Raises:
        TypeError: If connector_class doesn't inherit from DataConnector
        ValueError: If connector already registered and override=False

    Example:
        >>> class MyConnector(DataConnector):
        ...     # Implementation
        ...     pass
        >>> register_connector("mydb", MyConnector)
    """
    if not issubclass(connector_class, DataConnector):
        raise TypeError(
            f"{connector_class.__name__} must inherit from DataConnector"
        )

    if name in _CONNECTOR_REGISTRY and not override:
        raise ValueError(
            f"Connector '{name}' is already registered. "
            f"Use override=True to replace it."
        )

    _CONNECTOR_REGISTRY[name] = connector_class


def get_data_connector(
    connector_name: str, config: Optional[Any] = None, **kwargs: Any
) -> DataConnector:
    """Get a data connector by name.

    This is the main entry point for creating connector instances.
    It follows the same pattern as get_llm_provider() for consistency.

    Args:
        connector_name: Name of connector ('geo', 'ena', 'pdb', etc.)
        config: Optional connector-specific config object
        **kwargs: Additional connector-specific arguments

    Returns:
        DataConnector instance

    Raises:
        ValueError: If connector name not registered

    Example:
        >>> # Get GEO connector with default config
        >>> geo = get_data_connector("geo")
        >>> results = geo.search_datasets("melanoma immunotherapy")
        >>>
        >>> # Get connector with custom config
        >>> from quration.config import GEOConfig
        >>> custom_config = GEOConfig(email="[email protected]")
        >>> geo = get_data_connector("geo", config=custom_config)
    """
    if connector_name not in _CONNECTOR_REGISTRY:
        available = ", ".join(_CONNECTOR_REGISTRY.keys())
        raise ValueError(
            f"Unknown connector: '{connector_name}'. "
            f"Available connectors: {available}"
        )

    connector_class = _CONNECTOR_REGISTRY[connector_name]

    # Get config from global config if not provided
    if config is None:
        global_config = get_config()
        # Try to get connector-specific config
        if hasattr(global_config.data_sources, connector_name):
            config = getattr(global_config.data_sources, connector_name)

    # Create connector instance
    # Handle both connectors that require config and those that don't
    try:
        if config is not None:
            return connector_class(config=config, **kwargs)
        else:
            return connector_class(**kwargs)
    except TypeError:
        # If config not accepted, try without it
        return connector_class(**kwargs)


def list_available_connectors() -> list[str]:
    """List all available connector names.

    Returns:
        List of registered connector names

    Example:
        >>> connectors = list_available_connectors()
        >>> print(connectors)
        ['geo', 'ena', 'pdb', 'drugbank']
    """
    return sorted(list(_CONNECTOR_REGISTRY.keys()))


def get_connector_info(connector_name: str) -> Dict[str, Any]:
    """Get information about a specific connector.

    Args:
        connector_name: Name of connector

    Returns:
        Dictionary with connector information

    Raises:
        ValueError: If connector not found

    Example:
        >>> info = get_connector_info("geo")
        >>> print(info['class_name'])
        'GEOConnector'
    """
    if connector_name not in _CONNECTOR_REGISTRY:
        raise ValueError(f"Connector '{connector_name}' not found")

    connector_class = _CONNECTOR_REGISTRY[connector_name]

    # Create a temporary instance to get properties
    # This is safe because we're only reading properties, not executing methods
    try:
        # Try to create with minimal config
        temp_instance = connector_class()
    except (TypeError, ValueError, ImportError) as e:
        # If that fails, just get class-level info
        logger.debug(f"Could not instantiate {connector_name} connector: {e}")
        return {
            "name": connector_name,
            "class_name": connector_class.__name__,
            "module": connector_class.__module__,
        }

    return {
        "name": connector_name,
        "class_name": connector_class.__name__,
        "module": connector_class.__module__,
        "source_type": temp_instance.source_type.value,
        "supported_formats": [f.value for f in temp_instance.supported_export_formats],
    }


# Import and register built-in connectors
def _register_builtin_connectors() -> None:
    """Register all built-in connectors.

    This function is called automatically when the module is imported.
    """
    try:
        from quration.data_sources.geo_connector import GEOConnector

        register_connector("geo", GEOConnector, override=True)
    except ImportError:
        pass  # GEO connector not available

    # Register stub connectors for demo purposes
    try:
        from quration.data_sources.stubs import (
            ENAConnector,
            PDBConnector,
            DrugBankConnector,
        )

        register_connector("ena", ENAConnector, override=True)
        register_connector("pdb", PDBConnector, override=True)
        register_connector("drugbank", DrugBankConnector, override=True)
    except ImportError:
        pass  # Stub connectors not yet created


# Auto-register connectors when module is imported
_register_builtin_connectors()
