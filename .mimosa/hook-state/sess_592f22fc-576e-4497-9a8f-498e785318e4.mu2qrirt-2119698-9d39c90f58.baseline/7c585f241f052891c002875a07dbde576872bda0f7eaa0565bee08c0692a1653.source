"""Database connector base and registry."""

from abc import ABC, abstractmethod


class BaseConnector(ABC):
    """Abstract base for database connectors.

    All connectors enforce read-only access. Write operations must go through
    explicit service methods with authorization checks.
    """

    name: str = "base"
    _read_only: bool = True

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection."""
        ...

    @abstractmethod
    async def execute(self, sql: str) -> list[dict]:
        """Execute a read-only SQL query."""
        ...

    @abstractmethod
    async def get_schema(self) -> dict:
        """Retrieve table and column metadata."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        ...
