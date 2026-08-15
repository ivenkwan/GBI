"""Connector registry — maps data source types to connector classes."""

from app.connectors.base import BaseConnector

_registry: dict[str, type[BaseConnector]] = {}


def register_connector(name: str):
    """Decorator to register a connector class."""

    def decorator(cls: type[BaseConnector]) -> type[BaseConnector]:
        cls.name = name
        _registry[name] = cls
        return cls

    return decorator


def get_connector(name: str) -> type[BaseConnector] | None:
    """Look up a connector class by name."""
    return _registry.get(name)


def list_connectors() -> list[str]:
    """List all registered connector names."""
    return list(_registry.keys())


# Register built-in connectors
from app.connectors.postgresql_connector import PostgreSQLConnector  # noqa: E402

register_connector("postgresql")(PostgreSQLConnector)
