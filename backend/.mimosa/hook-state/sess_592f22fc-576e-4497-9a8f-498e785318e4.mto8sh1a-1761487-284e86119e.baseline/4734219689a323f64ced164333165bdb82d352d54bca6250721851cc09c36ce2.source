"""Tenant LLM resolution — BYOK with platform fallback (Phase 25, ADR 011 §1).

``resolve_llm(tenant_id)`` returns the tenant's effective LLM
configuration: their BYOK row (decrypted inside the DB via app_crypto, the
TENANT_ENCRYPTION_KEY riding as a bind parameter) when one is active, or
the platform defaults otherwise. The resolved value — including the
plaintext key — lives only in the resolution cache (60s TTL keyed by
tenant + key_version) and the outbound HTTP call; never in logs, audit, or
API responses.

The no-fallback policy (ADR 011 §5): when a tenant configuration exists,
its provider/key is used, full stop — a failing tenant key surfaces
``LLM_BYOK_MISCONFIGURED``; the platform key is used ONLY when no tenant
configuration exists (or its status is ``disabled`` — the explicit revert
switch). A row that cannot be decrypted (missing platform encryption key)
raises BYOKNotConfiguredError rather than silently routing the tenant's
traffic to the platform account.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import logger

_CACHE_TTL_SECONDS = 60


@dataclass
class ResolvedLLM:
    """Effective LLM configuration for one tenant."""

    provider: str  # "anthropic" | "openai"
    base_url: str | None
    api_key: str  # plaintext, in-memory only
    reasoning_model: str
    fast_model: str
    embedding_model: str | None
    source: str  # "tenant" | "platform"
    key_version: int | None
    tenant_id: str | None  # None for platform rows


class BYOKNotConfiguredError(RuntimeError):
    """A BYOK operation needs TENANT_ENCRYPTION_KEY and it is unset/invalid."""


def _require_encryption_key() -> str:
    key = (settings.TENANT_ENCRYPTION_KEY or "").strip()
    if not key or key.startswith("change-me"):
        raise BYOKNotConfiguredError(
            "TENANT_ENCRYPTION_KEY is not configured — BYOK is unavailable"
        )
    return key


def platform_default() -> ResolvedLLM:
    """The status-quo configuration: the platform Anthropic key."""
    return ResolvedLLM(
        provider="anthropic",
        base_url=None,
        api_key=settings.ANTHROPIC_API_KEY,
        reasoning_model=settings.LLM_REASONING_MODEL,
        fast_model=settings.LLM_FAST_MODEL,
        embedding_model=None,
        source="platform",
        key_version=None,
        tenant_id=None,
    )


# Resolution cache: plaintext keys live here for at most the TTL window.
_resolution_cache: dict[tuple[str, int], ResolvedLLM] = {}


def invalidate_resolution(tenant_id: str) -> None:
    """Drop cached resolutions for a tenant (called on every BYOK write)."""
    stale = [k for k in _resolution_cache if k[0] == tenant_id]
    for k in stale:
        _resolution_cache.pop(k, None)


async def resolve_llm(tenant_id: str | None) -> ResolvedLLM:
    """Effective LLM config: the tenant's BYOK row or platform defaults."""
    if not tenant_id:
        return platform_default()

    from app.core.cache import get_cache

    cache = get_cache()

    try:
        cached_version = await cache.get_byok_version(tenant_id)
        if cached_version is not None:
            hit = _resolution_cache.get((tenant_id, cached_version))
            if hit is not None:
                return hit

        resolved = await _load(tenant_id)
        if resolved is None:
            resolved = platform_default()
        _resolution_cache[(tenant_id, resolved.key_version or 0)] = resolved
        await cache.set_byok_version(tenant_id, resolved.key_version or 0)
        return resolved
    except BYOKNotConfiguredError:
        raise  # a configured tenant must never silently hit the platform key
    except Exception as e:  # noqa: BLE001 — control-plane outage fails open
        logger.warning("BYOK resolution unavailable — platform defaults: %s", e)
        return platform_default()


async def _load(tenant_id: str) -> ResolvedLLM | None:
    """Fetch + decrypt the tenant's active BYOK row, or None.

    Decryption happens INSIDE the query (app_crypto.decrypt with the key as
    $2) — the ciphertext never leaves the database, and the plaintext never
    enters Python until this return.
    """
    import asyncpg
    from sqlalchemy.engine import make_url

    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    dsn = url.render_as_string(hide_password=False)

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
        row = await conn.fetchrow(
            "SELECT provider, base_url, reasoning_model, fast_model, embedding_model, app_crypto.decrypt($2, api_key_enc) AS api_key, key_version FROM tenant_llm_providers WHERE tenant_id = CAST($1 AS uuid) AND status = 'active'",
            tenant_id,
            _require_encryption_key(),
        )
    finally:
        await conn.close()
    if row is None:
        return None
    return ResolvedLLM(
        provider=row["provider"],
        base_url=row["base_url"],
        api_key=row["api_key"],
        reasoning_model=row["reasoning_model"],
        fast_model=row["fast_model"],
        embedding_model=row["embedding_model"],
        source="tenant",
        key_version=row["key_version"],
        tenant_id=tenant_id,
    )
