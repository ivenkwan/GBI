"""Agent registry — maps agent names to their classes for dynamic dispatch."""

from app.agents.base import BaseAgent

# Agent registry — populated by the RouterAgent
_registry: dict[str, type[BaseAgent]] = {}


def register_agent(name: str):
    """Decorator to register an agent class in the global registry."""

    def decorator(cls: type[BaseAgent]) -> type[BaseAgent]:
        cls.name = name
        _registry[name] = cls
        return cls

    return decorator


def get_agent(name: str) -> type[BaseAgent] | None:
    """Look up an agent class by name."""
    return _registry.get(name)


def list_agents() -> list[str]:
    """List all registered agent names."""
    return list(_registry.keys())
