"""Platform superuser grants (Phase 21, ADR 009 §1).

One row per user in ``platform_admins``; an active superuser is a row with
``revoked_at IS NULL``. Grant is an upsert (re-grant clears the revocation),
revoke stamps ``revoked_by/at`` — history is kept, never deleted. Both
mutations refresh the 60-second ``platform_admin`` cache entry so an
unexpired JWT loses its power within a minute.
"""

import asyncpg

from app.core.auth import _admin_dsn
from app.core.cache import get_cache
from app.services.admin_audit import record_admin_action


async def grant_superadmin(user_id: str, granted_by: str) -> dict:
    """Grant (or re-grant) platform-superuser to a user. Raises on DB failure."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        row = await conn.fetchrow(
            "INSERT INTO platform_admins (user_id, granted_by) VALUES ($1::uuid, $2::uuid) ON CONFLICT (user_id) DO UPDATE SET granted_by = $2::uuid, granted_at = NOW(), revoked_by = NULL, revoked_at = NULL RETURNING user_id, granted_by, granted_at, revoked_at",
            user_id,
            granted_by,
        )
    finally:
        await conn.close()

    await get_cache().set_platform_admin(user_id, True)
    await record_admin_action(
        actor_user_id=granted_by,
        action="platform_admin.grant",
        target_type="user",
        target_id=user_id,
    )
    return {
        "user_id": str(row["user_id"]),
        "granted_by": str(row["granted_by"]) if row["granted_by"] else None,
        "granted_at": row["granted_at"].isoformat(),
        "revoked_at": None,
    }


async def revoke_superadmin(user_id: str, revoked_by: str) -> bool:
    """Revoke an active grant. False when there was nothing to revoke."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        updated = await conn.execute(
            "UPDATE platform_admins SET revoked_by = $2::uuid, revoked_at = NOW() WHERE user_id = $1::uuid AND revoked_at IS NULL",
            user_id,
            revoked_by,
        )
    finally:
        await conn.close()

    revoked = updated == "UPDATE 1"
    if revoked:
        await get_cache().set_platform_admin(user_id, False)
        await record_admin_action(
            actor_user_id=revoked_by,
            action="platform_admin.revoke",
            target_type="user",
            target_id=user_id,
        )
    return revoked


async def list_superadmins() -> list[dict]:
    """All grants with history (active first, most recent first)."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        rows = await conn.fetch(
            "SELECT user_id, granted_by, granted_at, revoked_by, revoked_at FROM platform_admins ORDER BY revoked_at NULLS FIRST, granted_at DESC"
        )
    finally:
        await conn.close()

    admins = []
    for row in rows:
        u = await _user_email(str(row["user_id"]))
        admins.append(
            {
                "user_id": str(row["user_id"]),
                "email": u,
                "granted_by": str(row["granted_by"]) if row["granted_by"] else None,
                "granted_at": row["granted_at"].isoformat(),
                "revoked_by": str(row["revoked_by"]) if row["revoked_by"] else None,
                "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
                "active": row["revoked_at"] is None,
            }
        )
    return admins


async def _user_email(user_id: str) -> str | None:
    """Best-effort email for the grant list (None when the user is gone)."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        return await conn.fetchval("SELECT email FROM users WHERE id = $1::uuid", user_id)
    finally:
        await conn.close()
