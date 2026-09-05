"""Provider adapter base types (Phase 25, ADR 011 §2)."""

from dataclasses import dataclass


class ProviderAuthError(Exception):
    """The provider rejected the credentials (401/403 class)."""


class ProviderRequestError(Exception):
    """The provider rejected the request (non-auth)."""


@dataclass
class AdapterResult:
    """Normalized response shared by both adapters."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AdapterCall:
    """One provider-agnostic call description."""

    messages: str  # single user turn (the house style)
    system: str | None
    model: str
    temperature: float
    max_tokens: int
    thinking: bool
    response_format: str | None  # "json" → provider-native structured output
    timeout: int


def invoke(
    provider: str, api_key: str, call: AdapterCall, base_url: str | None = None
) -> AdapterResult:
    """Dispatch to the provider adapter (sync — run in the async client's
    thread executor)."""
    if provider == "openai":
        from app.llm.providers.openai_provider import OpenAIAdapter

        return OpenAIAdapter(api_key=api_key, base_url=base_url).invoke(call)
    from app.llm.providers.anthropic_provider import AnthropicAdapter

    return AnthropicAdapter(api_key=api_key, base_url=base_url).invoke(call)
