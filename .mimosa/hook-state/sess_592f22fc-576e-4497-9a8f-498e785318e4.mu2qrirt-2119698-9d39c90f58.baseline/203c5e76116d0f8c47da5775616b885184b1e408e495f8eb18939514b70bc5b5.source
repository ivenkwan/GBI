"""OpenAI-format adapter (Phase 25, ADR 011 §2).

Chat completions via the existing ``openai`` SDK dependency, honoring a
custom ``base_url`` for OpenAI-compatible gateways. ``response_format ==
"json"`` maps to ``json_object`` (the shared extractor in LLMClient stays
as the fallback). ``thinking`` is a documented no-op: OpenAI reasoning is
selected by model name, not a flag.
"""

from app.llm.providers.base import AdapterCall, AdapterResult, ProviderAuthError

_AUTH_MARKERS = (
    "invalid_api_key",
    "incorrect api key",
    "unauthorized",
    "401",
    "403",
    "api key not valid",
    "authentication",
)


class OpenAIAdapter:
    def __init__(self, api_key: str, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = base_url

    def invoke(self, call: AdapterCall) -> AdapterResult:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key, base_url=self._base_url, timeout=call.timeout)

        request_kwargs: dict = {
            "model": call.model,
            "temperature": call.temperature,
            "max_tokens": call.max_tokens,
            "messages": [
                *([{"role": "system", "content": call.system}] if call.system else []),
                {"role": "user", "content": call.messages},
            ],
        }
        if call.response_format == "json":
            request_kwargs["response_format"] = {"type": "json_object"}
        # thinking: intentional no-op — reasoning is model-choice on OpenAI.

        try:
            response = client.chat.completions.create(**request_kwargs)
        except Exception as e:  # noqa: BLE001 — classified below
            text = str(e).lower()
            if any(marker in text for marker in _AUTH_MARKERS):
                raise ProviderAuthError(
                    f"openai-format endpoint rejected the credentials: {type(e).__name__}"
                ) from e
            raise

        choice = response.choices[0] if response.choices else None
        content = (choice.message.content if choice else "") or ""
        usage = getattr(response, "usage", None)
        return AdapterResult(
            content=content,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


class OpenAIChat:
    """LangChain-style wrapper the LLMClient can call like ChatAnthropic:
    ``ainvoke(messages, system=...)`` → object with ``.content`` and
    ``.usage_metadata``. Runs the sync SDK call in the default executor and
    maps auth failures to ProviderAuthError for the no-fallback policy."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: int,
        response_format: str | None,
    ):
        self._adapter = OpenAIAdapter(api_key=api_key, base_url=base_url)
        self._call_kwargs: dict = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "response_format": response_format,
        }

    async def ainvoke(self, messages, system: str = ""):
        import asyncio

        from app.llm.providers.base import AdapterCall

        user_text = messages[-1].content if messages else ""
        call = AdapterCall(
            messages=user_text,
            system=system or None,
            thinking=False,  # reasoning is model-choice on OpenAI
            **self._call_kwargs,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: self._adapter.invoke(call))
        return _LangchainLike(result)


class _LangchainLike:
    """Duck-types the subset of the ChatAnthropic response the client reads."""

    def __init__(self, result):
        self.content = result.content
        self.usage_metadata = {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
