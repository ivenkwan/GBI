"""Agent base classes — all GenBI agents inherit from BaseAgent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""

    model_name: str
    temperature: float = 0.0
    max_tokens: int = 4096
    thinking: bool = False  # Use Claude extended thinking for reasoning tasks


@dataclass
class AgentResult:
    """Standard result envelope from any agent execution."""

    agent_name: str
    success: bool
    output: dict
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    model_version: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BaseAgent(ABC):
    """Abstract base for all GenBI agents.

    Every agent must:
    - Accept typed input via `execute(**kwargs)`
    - Return a standardized `AgentResult`
    - Log input/output tokens, latency, and model version for audit
    - Never raise raw exceptions — errors go in AgentResult.errors
    """

    name: str = "base_agent"
    description: str = "Base agent class"

    def __init__(self, config: AgentConfig):
        self.config = config
        self._run_id = str(uuid4())

    @abstractmethod
    async def execute(self, **kwargs) -> AgentResult:
        """Execute the agent's core logic. Must be overridden by subclasses."""
        ...

    def _timed_result(self, result: AgentResult, start_time: float) -> AgentResult:
        """Attach latency and run metadata to an AgentResult."""
        result.latency_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
        return result
