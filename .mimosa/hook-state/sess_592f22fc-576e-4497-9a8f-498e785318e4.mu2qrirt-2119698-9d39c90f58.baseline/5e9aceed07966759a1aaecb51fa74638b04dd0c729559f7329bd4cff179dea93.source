"""Tenant isolation tests — the crown jewels of Phase 8b.

These tests prove that RLS is actually ENFORCED at the database layer:
the runtime role (genbi_app) sees only rows matching its tenant GUC, the
login role (genbi_auth) can read users but nothing else, and analytics
tables are tenant-scoped just like the metadata tables.

They connect with the real roles created by Alembic 0002 (dev default
passwords; overridable via GENBI_APP_DB_PASSWORD / GENBI_AUTH_DB_PASSWORD).
CI runs them against its service container after the migration step.
"""

import json
import uuid

import asyncpg
import pytest
import pytest_asyncio

from app.core.security import hash_password
from tests.conftest import admin_role_dsn, app_role_dsn, auth_role_dsn, db_reachable, owner_dsn

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())
PROBE_EMAIL_A = f"iso-a-{uuid.uuid4()}@genbi.local"
PROBE_EMAIL_B = f"iso-b-{uuid.uuid4()}@genbi.local"
PROBE_USER_A = uuid.uuid4()
PROBE_USER_B = uuid.uuid4()
PROBE_SALE_A = uuid.uuid4()


async def _set_guc(conn: asyncpg.Connection, tenant_id: str) -> None:
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)


async def _insert_probe_user(
    conn: asyncpg.Connection, tenant_id: str, user_id: uuid.UUID, email: str
) -> None:
    await _set_guc(conn, tenant_id)
    await conn.execute(
        "INSERT INTO users (id, tenant_id, email, hashed_password, roles) "
        "VALUES ($1, $2, $3, $4, $5::jsonb)",
        str(user_id),
        tenant_id,
        email,
        hash_password(email.split("@")[0]),
        json.dumps(["user"]),
    )


@pytest_asyncio.fixture(scope="module", autouse=True)
async def isolated_tenants():
    """Create two fresh tenants with one probe user (and one sale) each."""
    if not await db_reachable(app_role_dsn()):
        pytest.skip("Postgres (with Alembic 0002 roles) unavailable — skipping isolation tests")

    owner = await asyncpg.connect(owner_dsn())
    app = await asyncpg.connect(app_role_dsn())
    try:
        await owner.execute(
            "INSERT INTO tenants (id, name) VALUES ($1, $2), ($3, $4)",
            TENANT_A,
            "iso-test-a",
            TENANT_B,
            "iso-test-b",
        )
        await _insert_probe_user(app, TENANT_A, PROBE_USER_A, PROBE_EMAIL_A)
        await _insert_probe_user(app, TENANT_B, PROBE_USER_B, PROBE_EMAIL_B)

        # Analytics probe: one sale row owned by tenant A (sales has no FKs).
        await _set_guc(owner, TENANT_A)
        await owner.execute(
            "INSERT INTO sales (id, tenant_id, region, product_id, product_name, "
            "revenue, units, transaction_date, rep_id) "
            "VALUES ($1, $2, 'North', $3, 'IsoProbe', 1, 1, '2026-01-01', $4)",
            str(PROBE_SALE_A),
            TENANT_A,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        )

        yield
    finally:
        # Owner cleanup needs the GUC set per tenant (FORCE RLS binds it too).
        await _set_guc(owner, TENANT_A)
        await owner.execute("DELETE FROM users WHERE id = $1", str(PROBE_USER_A))
        await owner.execute("DELETE FROM sales WHERE id = $1", str(PROBE_SALE_A))
        await _set_guc(owner, TENANT_B)
        await owner.execute("DELETE FROM users WHERE id = $1", str(PROBE_USER_B))
        await owner.execute("DELETE FROM tenants WHERE id IN ($1, $2)", TENANT_A, TENANT_B)
        await app.close()
        await owner.close()


# ---------------------------------------------------------------------------
# genbi_app: tenant-scoped everywhere
# ---------------------------------------------------------------------------


async def test_app_role_sees_only_own_tenant_users():
    conn = await asyncpg.connect(app_role_dsn())
    try:
        await _set_guc(conn, TENANT_A)
        own = await conn.fetchval("SELECT count(*) FROM users WHERE email = $1", PROBE_EMAIL_A)
        other = await conn.fetchval("SELECT count(*) FROM users WHERE email = $1", PROBE_EMAIL_B)
        assert own == 1
        assert other == 0
    finally:
        await conn.close()


async def test_app_role_without_guc_sees_nothing():
    conn = await asyncpg.connect(app_role_dsn())
    try:
        visible = await conn.fetchval(
            "SELECT count(*) FROM users WHERE email IN ($1, $2)",
            PROBE_EMAIL_A,
            PROBE_EMAIL_B,
        )
        assert visible == 0
    finally:
        await conn.close()


async def test_app_role_cannot_insert_cross_tenant_rows():
    conn = await asyncpg.connect(app_role_dsn())
    try:
        await _set_guc(conn, TENANT_A)
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError) as exc_info:
            await conn.execute(
                "INSERT INTO users (id, tenant_id, email, hashed_password, roles) "
                "VALUES ($1, $2, $3, $4, $5::jsonb)",
                str(uuid.uuid4()),
                TENANT_B,  # forged tenant_id — must be rejected by WITH CHECK
                f"iso-forge-{uuid.uuid4()}@genbi.local",
                hash_password("forged-irrelevant"),
                json.dumps(["user"]),
            )
        assert "row-level security" in str(exc_info.value)
    finally:
        await conn.close()


async def test_analytics_tables_are_tenant_scoped():
    conn = await asyncpg.connect(app_role_dsn())
    try:
        await _set_guc(conn, TENANT_A)
        own = await conn.fetchval("SELECT count(*) FROM sales WHERE id = $1", str(PROBE_SALE_A))
        await _set_guc(conn, TENANT_B)
        other = await conn.fetchval("SELECT count(*) FROM sales WHERE id = $1", str(PROBE_SALE_A))
        assert own == 1
        assert other == 0
    finally:
        await conn.close()


async def test_analytics_without_guc_sees_nothing():
    conn = await asyncpg.connect(app_role_dsn())
    try:
        visible = await conn.fetchval("SELECT count(*) FROM sales WHERE id = $1", str(PROBE_SALE_A))
        assert visible == 0
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# genbi_admin: control-plane role (Phase 21 / ADR 009) — users + control
# tables across tenants, and NO business data.
# ---------------------------------------------------------------------------


async def test_admin_role_reads_users_across_tenants():
    conn = await asyncpg.connect(admin_role_dsn())
    try:
        visible = await conn.fetchval(
            "SELECT count(*) FROM users WHERE email IN ($1, $2)",
            PROBE_EMAIL_A,
            PROBE_EMAIL_B,
        )
        assert visible == 2
    finally:
        await conn.close()


async def test_admin_role_can_read_audit_log():
    # The one business-adjacent read granted to the control plane (SELECT only).
    conn = await asyncpg.connect(admin_role_dsn())
    try:
        await conn.fetchval("SELECT count(*) FROM audit_log")
    finally:
        await conn.close()


async def test_admin_role_cannot_read_business_tables():
    conn = await asyncpg.connect(admin_role_dsn())
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError) as exc_info:
            await conn.fetchval("SELECT count(*) FROM conversations")
        assert "permission denied" in str(exc_info.value)
    finally:
        await conn.close()


async def test_admin_role_cannot_write_business_tables():
    conn = await asyncpg.connect(admin_role_dsn())
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError) as exc_info:
            await conn.execute(
                "INSERT INTO conversations (id, tenant_id, title) VALUES ($1::uuid, $2::uuid, $3)",
                str(uuid.uuid4()),
                TENANT_A,
                "should be denied",
            )
        assert "permission denied" in str(exc_info.value)
    finally:
        await conn.close()


async def test_retired_auth_role_is_gone():
    # Phase 21 retired genbi_auth: its grants were revoked and the role
    # dropped by the 0008 RLS file. Connecting as it must fail.
    with pytest.raises((ConnectionError, asyncpg.exceptions.PostgresError)):
        conn = await asyncpg.connect(auth_role_dsn())
        try:
            await conn.fetchval("SELECT count(*) FROM users")
        finally:
            await conn.close()
