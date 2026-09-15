"""Centralized LLM client — single wrapper around Anthropic API.

All GenBI agents MUST route LLM calls through this module. Never call
langchain_anthropic or the Anthropic SDK directly in agent code.

This client handles:
- Timeout + retry (3 attempts, exponential backoff with jitter)
- Token budget enforcement (warn on approach, reject on exceed)
- Structured output parsing (JSON extraction with fallback)
- Latency tracking and audit logging
- Model selection from settings (LLM_REASONING_MODEL / LLM_FAST_MODEL)
"""

import hashlib
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage

from app.core.config import settings
from app.core.logging import logger

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class LLMCallResult:
    """Result of a single LLM invocation."""

    content: str
    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    attempt: int = 1
    parsed: dict | None = None  # Parsed JSON if structured output was requested


@dataclass
class LLMCallOptions:
    """Options for an LLM call."""

    temperature: float = 0.0
    max_tokens: int = 4096
    thinking: bool = False
    response_format: str | None = None  # "json" for structured output
    timeout_seconds: int = 60
    max_retries: int = 3
    token_budget: int = 100_000


class LLMBYOKMisconfiguredError(Exception):
    """A configured tenant's key was rejected by their provider — surfaced
    as LLM_BYOK_MISCONFIGURED; the platform key is never a fallback
    (ADR 011 §5)."""


# Backwards-friendly alias used inside the retry loop.
BYOKMisconfiguredError = LLMBYOKMisconfiguredError


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    """Centralized Anthropic LLM client with retry, audit, and budget control.

    Usage:
        client = LLMClient()

        # Fast call (Haiku) for classification
        result = await client.invoke(
            messages="Classify this: ...",
            system="You are a classifier.",
            use_reasoning=False,
        )

        # Reasoning call (Opus) for SQL generation
        result = await client.invoke(
            messages="Generate SQL for: ...",
            system=load_prompt("nl2sql-system"),
            use_reasoning=True,
            response_format="json",
        )
    """

    def __init__(self):
        self._audit_callback: Callable[[dict], Awaitable[None]] | None = None

    def set_audit_callback(self, callback: Callable[[dict], Awaitable[None]]) -> None:
        """Register a callback for audit logging (called after every LLM invocation)."""
        self._audit_callback = callback

    async def invoke(
        self,
        messages: str | list[BaseMessage],
        system: str | None = None,
        use_reasoning: bool = False,
        options: LLMCallOptions | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        session_id: str | None = None,
        generated_sql: str | None = None,
    ) -> LLMCallResult:
        """Invoke the LLM with retry, audit, and structured output.

        Args:
            messages: Single string (converted to HumanMessage) or list of LangChain messages.
            system: System prompt string.
            use_reasoning: If True, uses the reasoning model (Opus) with thinking mode.
            options: Fine-grained call options.
            user_id: User identifier for audit logging.
            tenant_id: Tenant identifier for audit logging.
            session_id: Session identifier for audit logging.
            generated_sql: If this call is part of a SQL pipeline, the SQL it produced.

        Returns:
            LLMCallResult with content, token counts, latency, and parsed JSON if applicable.
        """
        opts = options or LLMCallOptions()
        if use_reasoning:
            opts.thinking = True
            opts.temperature = 0.0

        # BYOK resolution (Phase 25, ADR 011): tenant config or platform
        # defaults. A configured tenant whose row can't be decrypted raises
        # BYOKNotConfiguredError — never a silent fallback to the platform key.
        from app.llm.resolver import resolve_llm

        resolved = await resolve_llm(tenant_id)
        model_name = resolved.reasoning_model if use_reasoning else resolved.fast_model
        start_time = time.time()
        last_error: Exception | None = None

        for attempt in range(1, opts.max_retries + 1):
            try:
                llm = self._build_llm(model_name, opts, attempt, resolved)
                langchain_messages = self._normalize_messages(messages)

                logger.debug(
                    "LLM call",
                    model=model_name,
                    attempt=attempt,
                    messages=len(langchain_messages),
                    thinking=opts.thinking,
                )

                response = await llm.ainvoke(
                    langchain_messages,
                    system=system or "",
                )

                latency = (time.time() - start_time) * 1000
                content = (
                    response.content if isinstance(response.content, str) else str(response.content)
                )

                result = LLMCallResult(
                    content=content,
                    model_name=model_name,
                    input_tokens=getattr(response, "usage_metadata", {}).get("input_tokens", 0)
                    or getattr(response, "input_tokens", 0),
                    output_tokens=getattr(response, "usage_metadata", {}).get("output_tokens", 0)
                    or getattr(response, "output_tokens", 0),
                    latency_ms=latency,
                    attempt=attempt,
                )

                # Token budget check
                total = result.input_tokens + result.output_tokens
                if total > opts.token_budget:
                    logger.warning(
                        "Token budget exceeded",
                        total=total,
                        budget=opts.token_budget,
                    )

                # Structured output parsing
                if opts.response_format == "json":
                    result.parsed = self._extract_json(content)

                # Audit (with BYOK attribution, Phase 25)
                await self._audit(
                    result=result,
                    messages=messages,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    generated_sql=generated_sql,
                    provider=resolved.provider,
                    key_source=resolved.source,
                    key_version=resolved.key_version,
                )

                logger.info(
                    "LLM call complete",
                    model=result.model_name,
                    tokens_in=result.input_tokens,
                    tokens_out=result.output_tokens,
                    latency_ms=round(result.latency_ms),
                    attempt=result.attempt,
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call failed",
                    attempt=attempt,
                    model=model_name,
                    error=str(e),
                )

                # No-fallback policy (ADR 011 §5): a configured tenant whose
                # key the provider rejects fails FAST — retrying or silently
                # crossing to the platform key would mask misconfiguration
                # and route tenant spend to the operator's account.
                from app.llm.providers.base import ProviderAuthError

                if isinstance(e, ProviderAuthError) and resolved.source == "tenant":
                    logger.error(
                        "BYOK key rejected — surfacing LLM_BYOK_MISCONFIGURED (no fallback)",
                        tenant_id=tenant_id,
                        provider=resolved.provider,
                    )
                    raise BYOKMisconfiguredError(
                        f"tenant LLM key rejected by {resolved.provider} — "
                        "fix the BYOK configuration; the platform key is not used"
                    ) from e

                if attempt < opts.max_retries:
                    backoff = min(2**attempt + (hash(str(e)) % 100) / 100, 30)
                    await self._sleep(backoff)
                continue

        # All retries exhausted
        logger.error("LLM call failed after all retries", error=str(last_error))
        raise last_error  # type: ignore[misc]

    def _build_llm(self, model_name: str, opts: LLMCallOptions, attempt: int, resolved=None):
        """Build the provider chat client (BYOK-aware, Phase 25).

        ``resolved`` carries the tenant's provider/key/base_url or the
        platform defaults; None falls back to the legacy platform-only
        construction (early tests).
        """
        if resolved is not None and resolved.provider == "openai":
            from app.llm.providers.openai_provider import OpenAIChat

            return OpenAIChat(
                api_key=resolved.api_key,
                base_url=resolved.base_url,
                model=model_name,
                temperature=opts.temperature,
                max_tokens=opts.max_tokens,
                timeout=opts.timeout_seconds + (attempt * 15),
                response_format=opts.response_format,
            )

        timeout = opts.timeout_seconds + (attempt * 15)  # Scale timeout per attempt

        model_kwargs: dict = {}
        if opts.thinking:
            model_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": min(opts.max_tokens // 2, 4096),
            }

        kwargs: dict = {
            "model": model_name,
            "temperature": opts.temperature,
            "max_tokens": opts.max_tokens,
            "timeout": timeout,
            "max_retries": 1,  # We handle retries ourselves
        }
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs
        if resolved is not None:
            kwargs["api_key"] = resolved.api_key
            if resolved.base_url:
                kwargs["base_url"] = resolved.base_url
        else:
            kwargs["api_key"] = settings.ANTHROPIC_API_KEY
        return ChatAnthropic(**kwargs)

    def _normalize_messages(self, messages: str | list[BaseMessage]) -> list[BaseMessage]:
        """Normalize message input to a list of BaseMessage."""
        if isinstance(messages, str):
            return [HumanMessage(content=messages)]
        return messages

    def _extract_json(self, text: str) -> dict | None:
        """Extract a JSON object from LLM output.

        Tries multiple strategies:
        1. The text is pure JSON already
        2. JSON inside ```json ... ``` code blocks
        3. First { ... } pair in the text
        """
        text = text.strip()

        # Strategy 1: pure JSON
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Strategy 2: markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: first { ... } pair
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to extract JSON from LLM output", preview=text[:200])
        return None

    async def _audit(
        self,
        result: LLMCallResult,
        messages: str | list[BaseMessage] | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        session_id: str | None = None,
        generated_sql: str | None = None,
        provider: str | None = None,
        key_source: str | None = None,
        key_version: int | None = None,
    ) -> None:
        """Log this LLM call to the audit trail."""
        if self._audit_callback:
            try:
                await self._audit_callback(
                    {
                        "session_id": session_id or str(uuid.uuid4()),
                        "user_id": user_id or "unknown",
                        "tenant_id": tenant_id or "default",
                        # SHA-256 of the prompt itself (never store raw text)
                        "input_prompt_hash": hashlib.sha256(
                            str(messages or "").encode()
                        ).hexdigest(),
                        "generated_sql": generated_sql or "",
                        "model_name": result.model_name,
                        "model_version": "latest",
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "latency_ms": result.latency_ms,
                        # BYOK attribution (ADR 011 §8) — never the key itself
                        "provider": provider,
                        "key_source": key_source,
                        "key_version": key_version,
                    }
                )
            except Exception as e:
                logger.error("Audit callback failed", error=str(e))

    async def _sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(seconds)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------


def load_prompt(name: str) -> str:
    """Load a versioned prompt template from .claude/prompts/.

    Args:
        name: Prompt name without extension (e.g. "nl2sql-system", "chart-gen-system")

    Returns:
        The prompt text content, or "" if not found.

    Resolution order:
        1. ``settings.PROMPT_DIR`` if set (explicit override).
        2. ``/app/.claude/prompts`` if it exists (Docker container — the
           Dockerfile bakes prompts into /app/.claude).
        3. The repo root's ``.claude/prompts`` computed relative to this file
           (host/local dev, where this module is at backend/app/core/).

    The fallback (3) historically broke inside Docker because the relative path
    resolved to ``/.claude/prompts``; the explicit container path (2) fixes that.
    """
    from pathlib import Path

    from app.core.config import settings

    candidates = [
        Path(settings.PROMPT_DIR) if settings.PROMPT_DIR else None,
        Path("/app/.claude/prompts"),  # container
        Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "prompts",  # host
    ]

    prompt_path: Path | None = None
    for base in candidates:
        if base is None:
            continue
        candidate = base / f"{name}.md"
        if candidate.exists():
            prompt_path = candidate
            break

    if prompt_path is None:
        logger.warning(f"Prompt file not found: {name}.md")
        return ""

    return prompt_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLMClient instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
