"""Anthropic-native adapter (Phase 25, ADR 011 §2).

Lifts the existing ``langchain_anthropic.ChatAnthropic`` path unchanged:
thinking mode via model_kwargs, ``max_tokens`` semantics, token counts from
usage_metadata. Auth failures map to ProviderAuthError so the client fails
fast under the no-fallback policy.
"""

from app.llm.providers.base import AdapterCall, AdapterResult, ProviderAuthError

_AUTH_MARKERS = (
    "authentication_error",
    "permission_error",
    "invalid x-api-key",
    "invalid api key",
    "unauthorized",
    "status_code 401",
    "status_code 403",
)


class AnthropicAdapter:
    def __init__(self, api_key: str, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = base_url

    def invoke(self, call: AdapterCall) -> AdapterResult:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        model_kwargs: dict = {}
        if call.thinking:
            model_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": min(call.max_tokens // 2, 4096),
            }

        kwargs: dict = {
            "model": call.model,
            "temperature": call.temperature,
            "max_tokens": call.max_tokens,
            "api_key": self._api_key,
            "timeout": call.timeout,
            "max_retries": 1,
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs

        llm = ChatAnthropic(**kwargs)
        try:
            response = llm.invoke([HumanMessage(content=call.messages)], system=call.system or "")
        except Exception as e:  # noqa: BLE001 — classified below
            text = str(e).lower()
            if any(marker in text for marker in _AUTH_MARKERS):
                raise ProviderAuthError(
                    f"anthropic rejected the credentials: {type(e).__name__}"
                ) from e
            raise

        content = response.content if isinstance(response.content, str) else str(response.content)
        usage = getattr(response, "usage_metadata", {}) or {}
        return AdapterResult(
            content=content,
            input_tokens=usage.get("input_tokens", 0) or getattr(response, "input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0) or getattr(response, "output_tokens", 0),
        )
