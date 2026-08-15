"""Audit writer — persists the per-LLM-call governance trail to audit_log.

Registered as the LLMClient audit callback at app startup (main.create_app):
every successful LLM invocation in the pipeline (router, nl2sql, chart,
narrative) lands one audit_log row with real token counts, latency, model
name, and any generated SQL — the "every LLM call produces an AuditLog
entry" contract from docs/architecture-overview.md, and agent-granularity
tracing per ADR 002.

Writes go through a dedicated asyncpg connection on the RLS-bound runtime
role (genbi_app) with the tenant GUC set per row — the same isolation
pattern as the rest of the app (ADR 006). Rows whose ids are not UUIDs
(the client's "unknown"/"default" fallbacks) are skipped: better a missing
row than a broken chat response.

Everything FAILS OPEN: audit problems are logged, never raised — an audit
outage must not take down the pipeline (docs/core-services.md).
"""

import uuid

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger

# Inline literal with $n parameters (identifiers fixed; values bound).
_AUDIT_INSERT = (
    "INSERT INTO audit_log "
    "(session_id, user_id, tenant_id, input_prompt_hash, generated_sql, "
    "model_name, model_version, input_tokens, output_tokens, latency_ms) "
    "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10)"
)


def _dsn() -> str:
    """asyncpg DSN for the runtime role (DATABASE_URL, plain driver)."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _as_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


async def write_audit_entry(entry: dict) -> None:
    """Persist one LLM-call audit entry. Never raises."""
    session_id = _as_uuid(entry.get("session_id", ""))
    user_id = _as_uuid(entry.get("user_id", ""))
    tenant_id = _as_uuid(entry.get("tenant_id", ""))
    if session_id is None or user_id is None or tenant_id is None:
        logger.warning(
            "Audit entry skipped — non-UUID identity fields",
            user_id=entry.get("user_id"),
            tenant_id=entry.get("tenant_id"),
        )
        return

    try:
        conn = await asyncpg.connect(_dsn())
        try:
            await conn.execute(
                "SELECT set_config('app.current_tenant_id', $1, false)",
                str(tenant_id),
            )
            async with conn.transaction():
                await conn.execute(
                    _AUDIT_INSERT,
                    str(session_id),
                    str(user_id),
                    str(tenant_id),
                    str(entry.get("input_prompt_hash", ""))[:64],
                    entry.get("generated_sql") or None,
                    str(entry.get("model_name", "unknown"))[:100],
                    str(entry.get("model_version", "unknown"))[:50],
                    int(entry.get("input_tokens", 0) or 0),
                    int(entry.get("output_tokens", 0) or 0),
                    float(entry.get("latency_ms", 0) or 0),
                )
        finally:
            await conn.close()
    except Exception as e:
        # Fail open — an audit outage must never break the chat pipeline.
        logger.error("Audit write failed (non-fatal): %s", e)
