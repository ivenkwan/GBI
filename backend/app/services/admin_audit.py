"""Admin-action audit writer (Phase 21, ADR 009 §5).

Every control-plane mutation (tenant lifecycle, superuser grants) lands a
row in ``admin_audit``. Writes are fail-open — an audit outage must never
block an admin operation — and never raise to the caller.
"""

import json
import uuid

import asyncpg

from app.core.auth import _admin_dsn
from app.core.logging import logger


async def record_admin_action(
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str | None = None,
    detail: dict | None = None,
) -> bool:
    """Append one admin_audit row. Fail-open (False + warning on failure)."""
    try:
        conn = await asyncpg.connect(_admin_dsn())
        try:
            await conn.execute(
                "INSERT INTO admin_audit (actor_user_id, action, target_type, target_id, detail) VALUES ($1::uuid, $2, $3, $4, $5::jsonb)",
                actor_user_id,
                action[:100],
                target_type[:50],
                str(target_id)[:100] if target_id else None,
                json.dumps(detail) if detail else None,
            )
        finally:
            await conn.close()
        return True
    except Exception as e:  # noqa: BLE001 — audit must never break an admin op
        logger.warning("Admin audit write failed (non-fatal): %s", e)
        return False


def new_audit_id() -> str:
    """Standalone id generator for call sites that want correlation ids."""
    return str(uuid.uuid4())
