"""Tenant lifecycle service (Phase 21, ADR 009 §4).

Control-plane operations on the ``genbi_admin`` role (DML on
tenants/users/platform_admins/admin_audit, nothing else). Per-tenant
business counters in the detail view use short-lived ``genbi_app``
connections with the tenant GUC set — the admin role can read no business
data (ADR 009 §3). Decommission additionally cleans analytics rows as the
owner with the tenant GUC (analytics tables have no tenant FK to cascade).

Every mutation writes an ``admin_audit`` row (fail-open) and refreshes the
60-second tenant-status cache on status changes. All statements are static
literals with ``$N`` binds — table names are never interpolated.
"""

import json
import uuid
from datetime import UTC, datetime

import asyncpg
from sqlalchemy.engine import make_url

from app.core.auth import _admin_dsn
from app.core.cache import get_cache
from app.core.config import settings
from app.core.logging import logger
from app.core.security import hash_password
from app.services.admin_audit import record_admin_action


class TenantExistsError(Exception):
    """A tenant with the same name or slug already exists."""


class UserExistsError(Exception):
    """The initial admin email already exists in the tenant."""


class TenantNotEmptyError(Exception):
    """Decommission refused: the tenant still has users (use force)."""


def _app_dsn() -> str:
    """asyncpg DSN for the RLS-bound runtime role (business counters)."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _owner_dsn() -> str:
    """asyncpg DSN for the owner role (analytics cleanup on decommission)."""
    url = make_url(settings.DATABASE_URL_SYNC)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _app_connect(tenant_id: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_app_dsn())
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
    return conn


# ---------------------------------------------------------------------------
# Provision
# ---------------------------------------------------------------------------


async def provision_tenant(
    name: str,
    slug: str,
    admin_email: str,
    admin_password: str,
    actor_user_id: str,
    seed_sample_data: bool = False,
) -> dict:
    """Create a tenant + its initial admin user in one transaction.

    Optional sample data (a handful of sales rows) lands via the runtime
    role with the tenant GUC — after the transaction commits.
    """
    email = admin_email.strip().lower()
    hashed = hash_password(admin_password)
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    roles = json.dumps(["admin", "user"])

    conn = await asyncpg.connect(_admin_dsn())
    try:
        async with conn.transaction():
            try:
                await conn.execute(
                    "INSERT INTO tenants (id, name, slug, status) VALUES ($1::uuid, $2, $3, 'active')",
                    tenant_id,
                    name,
                    slug,
                )
            except asyncpg.UniqueViolationError as e:
                raise TenantExistsError(f"name or slug already in use: {slug}") from e
            try:
                await conn.execute(
                    "INSERT INTO users (id, tenant_id, email, hashed_password, roles) VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb)",
                    user_id,
                    tenant_id,
                    email,
                    hashed,
                    roles,
                )
            except asyncpg.UniqueViolationError as e:
                raise UserExistsError(f"user already exists: {email}") from e
    finally:
        await conn.close()

    if seed_sample_data:
        try:
            await _seed_sample_data(tenant_id)
        except Exception as e:  # noqa: BLE001 — seeding is best-effort
            logger.warning("Sample data seeding failed (non-fatal): %s", e)

    await record_admin_action(
        actor_user_id=actor_user_id,
        action="tenant.provision",
        target_type="tenant",
        target_id=tenant_id,
        detail={"name": name, "slug": slug, "admin_email": email, "seeded": seed_sample_data},
    )
    await get_cache().set_tenant_status(tenant_id, "active")

    return {
        "tenant_id": tenant_id,
        "name": name,
        "slug": slug,
        "status": "active",
        "admin_user_id": user_id,
        "admin_email": email,
        "seeded": seed_sample_data,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def _seed_sample_data(tenant_id: str) -> None:
    """A few demo sales rows so a fresh tenant is immediately queryable."""
    conn = await _app_connect(tenant_id)
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO sales (id, tenant_id, region, product_id, product_name, revenue, units, transaction_date, rep_id) VALUES ($1::uuid, $2::uuid, 'North', $3::uuid, 'Sample Product', 1200.0, 12, '2026-01-15', $4::uuid)",
                str(uuid.uuid4()),
                tenant_id,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            await conn.execute(
                "INSERT INTO sales (id, tenant_id, region, product_id, product_name, revenue, units, transaction_date, rep_id) VALUES ($1::uuid, $2::uuid, 'South', $3::uuid, 'Sample Product', 800.0, 8, '2026-02-15', $4::uuid)",
                str(uuid.uuid4()),
                tenant_id,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
            await conn.execute(
                "INSERT INTO sales (id, tenant_id, region, product_id, product_name, revenue, units, transaction_date, rep_id) VALUES ($1::uuid, $2::uuid, 'East', $3::uuid, 'Sample Product', 950.0, 9, '2026-03-15', $4::uuid)",
                str(uuid.uuid4()),
                tenant_id,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            )
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def list_tenants(limit: int = 100) -> list[dict]:
    """Tenant list with user counts, newest first. Raises on DB failure."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        rows = await conn.fetch(
            "SELECT t.id, t.name, t.slug, t.status, t.created_at, (SELECT count(*) FROM users u WHERE u.tenant_id = t.id) AS user_count FROM tenants t ORDER BY t.created_at DESC LIMIT $1",
            limit,
        )
    finally:
        await conn.close()
    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "slug": row["slug"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat(),
            "user_count": row["user_count"],
        }
        for row in rows
    ]


async def get_tenant(tenant_id: str) -> dict | None:
    """Tenant detail: row + users + business counters + recent admin audit.

    Business counters (conversations/reports/dashboards/schedules) run on
    the runtime role with this tenant's GUC — genbi_admin reads no business
    data by design.
    """
    conn = await asyncpg.connect(_admin_dsn())
    try:
        row = await conn.fetchrow(
            "SELECT id, name, slug, status, settings, created_at, updated_at FROM tenants WHERE id = $1::uuid",
            tenant_id,
        )
        if row is None:
            return None
        users = await conn.fetch(
            "SELECT id, email, roles, created_at FROM users WHERE tenant_id = $1::uuid ORDER BY created_at",
            tenant_id,
        )
        audit_rows = await conn.fetch(
            "SELECT actor_user_id, action, target_type, target_id, detail, created_at FROM admin_audit WHERE target_id = $1 OR detail->>'tenant_id' = $1 ORDER BY created_at DESC LIMIT 20",
            tenant_id,
        )
    finally:
        await conn.close()

    counters = await _business_counters(tenant_id)

    settings_json = row["settings"]
    if isinstance(settings_json, str):
        settings_json = json.loads(settings_json)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "slug": row["slug"],
        "status": row["status"],
        "settings": settings_json or {},
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "user_count": len(users),
        "users": [
            {
                "id": str(u["id"]),
                "email": u["email"],
                # Raw asyncpg returns JSONB as text
                "roles": list(
                    (json.loads(u["roles"]) if isinstance(u["roles"], str) else u["roles"])
                    or ["user"]
                ),
                "created_at": u["created_at"].isoformat(),
            }
            for u in users
        ],
        "counters": counters,
        "recent_admin_actions": [
            {
                "actor_user_id": str(a["actor_user_id"]),
                "action": a["action"],
                "target_type": a["target_type"],
                "target_id": a["target_id"],
                "created_at": a["created_at"].isoformat(),
            }
            for a in audit_rows
        ],
    }


async def _business_counters(tenant_id: str) -> dict:
    """Conversations/reports/dashboards/schedules counts via the runtime
    role + tenant GUC. Fail-open to -1s (detail still renders)."""
    counters = {"conversations": -1, "reports": -1, "dashboards": -1, "report_schedules": -1}
    try:
        conn = await _app_connect(tenant_id)
        try:
            counters["conversations"] = await conn.fetchval("SELECT count(*) FROM conversations")
            counters["reports"] = await conn.fetchval("SELECT count(*) FROM reports")
            counters["dashboards"] = await conn.fetchval("SELECT count(*) FROM dashboards")
            counters["report_schedules"] = await conn.fetchval(
                "SELECT count(*) FROM report_schedules"
            )
        finally:
            await conn.close()
        counters = {k: int(v or 0) for k, v in counters.items()}
    except Exception as e:  # noqa: BLE001 — counters are best-effort
        logger.warning("Tenant business counters unavailable (non-fatal): %s", e)
        counters = {k: -1 for k in counters}
    return counters


async def platform_stats() -> dict:
    """Platform counters for /admin/stats. Raises on DB failure."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        tenants_total = await conn.fetchval("SELECT count(*) FROM tenants") or 0
        tenants_active = (
            await conn.fetchval("SELECT count(*) FROM tenants WHERE status = 'active'") or 0
        )
        users_total = await conn.fetchval("SELECT count(*) FROM users") or 0
        # One pass over the 24h audit window: call count (as before), token
        # total, and the BYOK share — spend attribution lives in audit_log
        # (ADR 011 §8), no separate metering table.
        usage = await conn.fetchrow(
            "SELECT count(*) AS calls, COALESCE(sum(input_tokens + output_tokens), 0) AS tokens, count(*) FILTER (WHERE key_source = 'tenant') AS byok_calls FROM audit_log WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        llm_calls_24h = (usage["calls"] if usage else 0) or 0
        platform_admins_active = (
            await conn.fetchval("SELECT count(*) FROM platform_admins WHERE revoked_at IS NULL")
            or 0
        )
    finally:
        await conn.close()
    return {
        "tenants_total": tenants_total,
        "tenants_active": tenants_active,
        "tenants_suspended": tenants_total - tenants_active,
        "users_total": users_total,
        "llm_calls_24h": llm_calls_24h,
        "llm_tokens_24h": (usage["tokens"] if usage else 0) or 0,
        "llm_byok_calls_24h": (usage["byok_calls"] if usage else 0) or 0,
        "platform_admins_active": platform_admins_active,
    }


# ---------------------------------------------------------------------------
# Updates / decommission
# ---------------------------------------------------------------------------


async def update_tenant(
    tenant_id: str,
    actor_user_id: str,
    name: str | None = None,
    status: str | None = None,
    settings_patch: dict | None = None,
) -> dict | None:
    """Rename / suspend / activate / merge settings. None when not found.

    Field-specific static statements (one per provided field) inside one
    transaction; a status change refreshes the 60s status cache.
    """
    conn = await asyncpg.connect(_admin_dsn())
    try:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT id, name, slug, status, settings FROM tenants WHERE id = $1::uuid",
                tenant_id,
            )
            if existing is None:
                return None

            if name is not None:
                await conn.execute(
                    "UPDATE tenants SET name = $2, updated_at = NOW() WHERE id = $1::uuid",
                    tenant_id,
                    name,
                )
            if status is not None:
                await conn.execute(
                    "UPDATE tenants SET status = $2, updated_at = NOW() WHERE id = $1::uuid",
                    tenant_id,
                    status,
                )
            if settings_patch is not None:
                merged = dict(existing["settings"] or {})
                merged.update(settings_patch)
                await conn.execute(
                    "UPDATE tenants SET settings = $2::jsonb, updated_at = NOW() WHERE id = $1::uuid",
                    tenant_id,
                    json.dumps(merged),
                )
    finally:
        await conn.close()

    if status is not None:
        await get_cache().set_tenant_status(tenant_id, status)

    await record_admin_action(
        actor_user_id=actor_user_id,
        action="tenant.update",
        target_type="tenant",
        target_id=tenant_id,
        detail={"name": name, "status": status, "settings_patch": settings_patch},
    )
    return await get_tenant(tenant_id)


async def decommission_tenant(tenant_id: str, actor_user_id: str, force: bool = False) -> bool:
    """Delete a tenant and its data. Refuses non-empty tenants unless force.

    FK cascades remove users/conversations/reports/dashboards/schedules/
    embeddings/examples; analytics rows (no tenant FK) are cleaned
    explicitly as the owner with the tenant GUC; audit_log history is
    retained by design (its tenant FK was dropped in 0008). All statements
    are static — the analytics cleanup unrolls one literal DELETE per table.
    """
    conn = await asyncpg.connect(_admin_dsn())
    try:
        user_count = await conn.fetchval(
            "SELECT count(*) FROM users WHERE tenant_id = $1::uuid", tenant_id
        )
        exists = await conn.fetchval("SELECT 1 FROM tenants WHERE id = $1::uuid", tenant_id)
        if not exists:
            return False
        if user_count and not force:
            raise TenantNotEmptyError(
                f"tenant still has {user_count} user(s) — pass force to delete"
            )
    finally:
        await conn.close()

    # Analytics cleanup first (owner + tenant GUC). One literal statement
    # per table — table names are never built from variables. Each table
    # fails open: a database without the analytics tables (0003 stamped
    # over) must still decommission cleanly.
    import contextlib

    owner = await asyncpg.connect(_owner_dsn())
    try:
        # No wrapping transaction: per-table independence — a missing table
        # must not abort the others' cleanup.
        await owner.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM transactions")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM orders")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM sales")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM deals")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM web_users")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM customers")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM sales_representatives")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM products")
        with contextlib.suppress(Exception):
            await owner.execute("DELETE FROM regions")
    finally:
        await owner.close()

    # The tenant delete cascades the FK'd business tables.
    conn = await asyncpg.connect(_admin_dsn())
    try:
        deleted = await conn.execute("DELETE FROM tenants WHERE id = $1::uuid", tenant_id)
    finally:
        await conn.close()

    await get_cache().set_tenant_status(tenant_id, "deleted")
    await record_admin_action(
        actor_user_id=actor_user_id,
        action="tenant.decommission",
        target_type="tenant",
        target_id=tenant_id,
        detail={"force": force},
    )
    return deleted == "DELETE 1"
