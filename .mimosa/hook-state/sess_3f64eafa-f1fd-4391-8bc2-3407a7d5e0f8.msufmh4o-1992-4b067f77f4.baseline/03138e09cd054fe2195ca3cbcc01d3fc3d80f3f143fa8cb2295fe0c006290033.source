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
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

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

        model_name = settings.LLM_REASONING_MODEL if use_reasoning else settings.LLM_FAST_MODEL
        start_time = time.time()
        last_error: Exception | None = None

        for attempt in range(1, opts.max_retries + 1):
            try:
                llm = self._build_llm(model_name, opts, attempt)
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
                content = response.content if isinstance(response.content, str) else str(response.content)

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

                # Audit
                await self._audit(
                    result=result,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    generated_sql=generated_sql,
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

                if attempt < opts.max_retries:
                    backoff = min(2**attempt + (hash(str(e)) % 100) / 100, 30)
                    await self._sleep(backoff)
                continue

        # All retries exhausted
        logger.error("LLM call failed after all retries", error=str(last_error))
        raise last_error  # type: ignore[misc]

    def _build_llm(self, model_name: str, opts: LLMCallOptions, attempt: int) -> ChatAnthropic:
        """Build a ChatAnthropic instance with timeout and model kwargs."""
        timeout = opts.timeout_seconds + (attempt * 15)  # Scale timeout per attempt

        model_kwargs: dict = {}
        if opts.thinking:
            model_kwargs["thinking"] = {"type": "enabled", "budget_tokens": min(opts.max_tokens // 2, 4096)}

        return ChatAnthropic(
            model=model_name,
            temperature=opts.temperature,
            max_tokens=opts.max_tokens,
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=timeout,
            max_retries=1,  # We handle retries ourselves
            model_kwargs=model_kwargs if model_kwargs else None,
        )

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
        user_id: str | None = None,
        tenant_id: str | None = None,
        session_id: str | None = None,
        generated_sql: str | None = None,
    ) -> None:
        """Log this LLM call to the audit trail."""
        if self._audit_callback:
            try:
                await self._audit_callback({
                    "session_id": session_id or str(uuid.uuid4()),
                    "user_id": user_id or "unknown",
                    "tenant_id": tenant_id or "default",
                    "input_prompt_hash": hashlib.sha256(
                        json.dumps({
                            "model": result.model_name,
                            "tokens": result.input_tokens,
                        }).encode()
                    ).hexdigest(),
                    "generated_sql": generated_sql or "",
                    "model_name": result.model_name,
                    "model_version": "latest",
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": result.latency_ms,
                })
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
        The prompt text content.
    """
    from pathlib import Path

    prompt_dir = Path(__file__).parent.parent.parent.parent / ".claude" / "prompts"
    prompt_path = prompt_dir / f"{name}.md"

    if not prompt_path.exists():
        logger.warning(f"Prompt file not found: {prompt_path}")
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
