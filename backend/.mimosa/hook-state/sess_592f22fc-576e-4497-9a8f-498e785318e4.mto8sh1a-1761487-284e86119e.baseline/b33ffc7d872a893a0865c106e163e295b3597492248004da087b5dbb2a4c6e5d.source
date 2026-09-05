"""BYOK storage service (Phase 25, ADR 011 §3-4, 6-7).

CRUD for the tenant's LLM provider configuration on the RLS-bound runtime
role with the tenant GUC: the API key is encrypted INSIDE the database
(app_crypto.encrypt, the platform key riding as a bind parameter) — Python
never sees the ciphertext it writes nor constructs it; reads return only
masked metadata (provider, models, base_url, key_last4, key_version,
status). Every write bumps key_version (the resolver's cache-invalidation
pointer) and drops cached resolutions immediately.
"""

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger
from app.llm.resolver import _require_encryption_key, invalidate_resolution

ALLOWED_PROVIDERS = frozenset({"anthropic", "openai"})


class BYOKValidationError(Exception):
    """The candidate config failed its live validation ping."""


def _dsn() -> str:
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _connect(tenant_id: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
    return conn


async def validate_provider(provider: str, api_key: str, base_url: str | None, model: str) -> None:
    """Live 1-token ping; raises BYOKValidationError with a sanitized message."""
    from app.llm.providers.base import AdapterCall, ProviderAuthError

    call = AdapterCall(
        messages="ping",
        system=None,
        model=model,
        temperature=0.0,
        max_tokens=1,
        thinking=False,
        response_format=None,
        timeout=15,
    )
    try:
        from app.llm.providers.base import invoke

        invoke(provider, api_key, call, base_url=base_url)
    except ProviderAuthError as e:
        raise BYOKValidationError(f"{provider} rejected the credentials") from e
    except BYOKValidationError:
        raise
    except Exception as e:  # noqa: BLE001 — sanitized, never the raw error
        raise BYOKValidationError(f"validation ping failed: {type(e).__name__}") from e


async def set_provider_config(
    tenant_id: str,
    provider: str,
    api_key: str,
    reasoning_model: str,
    fast_model: str,
    embedding_model: str | None = None,
    base_url: str | None = None,
    actor_user_id: str | None = None,
    validate: bool = True,
) -> dict:
    """Create/replace the tenant's BYOK config (validated). Masked return."""
    if provider not in ALLOWED_PROVIDERS:
        raise BYOKValidationError(f"provider must be one of {sorted(ALLOWED_PROVIDERS)}")
    if not api_key or len(api_key) < 8:
        raise BYOKValidationError("api_key looks too short to be real")

    if validate:
        await validate_provider(provider, api_key, base_url, fast_model)

    key = _require_encryption_key()  # BYOKNotConfiguredError when unset
    last4 = api_key[-4:]

    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "INSERT INTO tenant_llm_providers (tenant_id, provider, base_url, reasoning_model, fast_model, embedding_model, api_key_enc, key_last4, key_version, status, updated_by) VALUES ($1::uuid, $2, $3, $4, $5, $6, app_crypto.encrypt($7, $8), $9, 1, 'active', $10::uuid) ON CONFLICT (tenant_id) DO UPDATE SET provider = $2, base_url = $3, reasoning_model = $4, fast_model = $5, embedding_model = $6, api_key_enc = app_crypto.encrypt($7, $8), key_last4 = $9, key_version = tenant_llm_providers.key_version + 1, status = 'active', updated_by = $10::uuid, updated_at = NOW() RETURNING provider, base_url, reasoning_model, fast_model, embedding_model, key_last4, key_version, status, updated_at",
            tenant_id,
            provider,
            base_url,
            reasoning_model,
            fast_model,
            embedding_model,
            key,
            api_key,
            last4,
            actor_user_id,
        )
    finally:
        await conn.close()

    invalidate_resolution(tenant_id)

    from app.services.admin_audit import record_admin_action

    await record_admin_action(
        actor_user_id=actor_user_id or tenant_id,
        action="byok.set_provider",
        target_type="tenant",
        target_id=tenant_id,
        detail={"provider": provider, "key_version": row["key_version"]},
    )
    logger.info(
        "BYOK config saved",
        provider=provider,
        key_version=row["key_version"],
        tenant_id=tenant_id,
    )
    return _masked(row)


async def get_provider_config(tenant_id: str) -> dict | None:
    """Masked view — the key never leaves the database."""
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT provider, base_url, reasoning_model, fast_model, embedding_model, key_last4, key_version, status, updated_at FROM tenant_llm_providers WHERE tenant_id = $1::uuid",
            tenant_id,
        )
    finally:
        await conn.close()
    return _masked(row) if row else None


async def delete_provider_config(tenant_id: str, actor_user_id: str | None = None) -> bool:
    """Remove the config — LLM calls revert to the platform key."""
    conn = await _connect(tenant_id)
    try:
        deleted = await conn.execute(
            "DELETE FROM tenant_llm_providers WHERE tenant_id = $1::uuid",
            tenant_id,
        )
    finally:
        await conn.close()
    invalidate_resolution(tenant_id)
    return deleted == "DELETE 1"


async def set_status(tenant_id: str, status: str, actor_user_id: str | None = None) -> bool:
    """active/disabled kill switch — disabled is the explicit revert."""
    conn = await _connect(tenant_id)
    try:
        updated = await conn.execute(
            "UPDATE tenant_llm_providers SET status = $2, updated_by = $3::uuid, updated_at = NOW() WHERE tenant_id = $1::uuid",
            tenant_id,
            status,
            actor_user_id,
        )
    finally:
        await conn.close()
    invalidate_resolution(tenant_id)
    return updated == "UPDATE 1"


def _masked(row) -> dict:
    return {
        "provider": row["provider"],
        "base_url": row["base_url"],
        "reasoning_model": row["reasoning_model"],
        "fast_model": row["fast_model"],
        "embedding_model": row["embedding_model"],
        "key_last4": row["key_last4"],
        "key_version": row["key_version"],
        "status": row["status"],
        "updated_at": row["updated_at"].isoformat(),
    }
