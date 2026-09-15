"""Phase 21 control-plane service tests: platform admins, tenant lifecycle,
admin audit — all DB access faked via MagicMock connections (offline,
CI-safe; no DB drivers are touched)."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import verify_password
from app.services import platform_admins, tenants
from app.services.admin_audit import record_admin_action
from app.services.tenants import (
    TenantExistsError,
    TenantNotEmptyError,
    UserExistsError,
    decommission_tenant,
    provision_tenant,
    update_tenant,
)

TENANT = "00000000-0000-0000-0000-000000000001"
ACTOR = "00000000-0000-0000-0000-0000000000aa"
GRANTEE = "00000000-0000-0000-0000-0000000000bb"


def fake_conn(
    monkeypatch, module, *, fetch_rows=None, fetch_row=None, fetch_vals=None, execute_results=None
):
    """Patch module.asyncpg.connect with a MagicMock connection.

    Scriptable per-call results via lists (each entry consumed once):
    fetch_rows → list of row-lists, fetch_vals → list of scalars,
    execute_results → list of status strings / exceptions.
    """
    conn = MagicMock()
    conn.close = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    fetch_rows = list(fetch_rows or [])
    fetch_vals = list(fetch_vals or [])
    execute_results = list(execute_results or [])

    async def fetch_side_effect(sql, *args):
        if fetch_rows:
            out = fetch_rows.pop(0)
            if isinstance(out, Exception):
                raise out
            return out
        return []

    async def fetchrow_side_effect(sql, *args):
        rows = await fetch_side_effect(sql, *args)
        return rows[0] if rows else None

    async def fetchval_side_effect(sql, *args):
        if fetch_vals:
            out = fetch_vals.pop(0)
            if isinstance(out, Exception):
                raise out
            return out
        rows = await fetch_side_effect(sql, *args)
        return rows[0] if rows else None

    async def execute_side_effect(sql, *args):
        if execute_results:
            out = execute_results.pop(0)
            if isinstance(out, Exception):
                raise out
            return out
        return "INSERT 0 1"

    conn.fetch = AsyncMock(side_effect=fetch_side_effect)
    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
    conn.execute = AsyncMock(side_effect=execute_side_effect)

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(module.asyncpg, "connect", fake_connect)
    return conn


@pytest.fixture
def no_audit(monkeypatch):
    mock = AsyncMock(return_value=True)
    # Services bind record_admin_action at module import — patch it where
    # they hold it, not (only) where it's defined.
    monkeypatch.setattr(tenants, "record_admin_action", mock)
    monkeypatch.setattr(platform_admins, "record_admin_action", mock)
    monkeypatch.setattr("app.services.admin_audit.record_admin_action", mock)
    return mock


@pytest.fixture
def cache_mock(monkeypatch):
    cache = MagicMock()
    cache.set_tenant_status = AsyncMock()
    cache.set_platform_admin = AsyncMock()
    # The services bind get_cache at module import — patch it where they
    # hold it (plus the core module for auth paths).
    monkeypatch.setattr(tenants, "get_cache", lambda: cache)
    monkeypatch.setattr(platform_admins, "get_cache", lambda: cache)
    monkeypatch.setattr("app.core.cache.get_cache", lambda: cache)
    return cache


def _sqls(mock, kind="execute"):
    return [call.args[0] for call in mock.call_args_list]


# ---------------------------------------------------------------------------
# platform_admins
# ---------------------------------------------------------------------------


async def test_grant_upserts_and_refreshes_cache(monkeypatch, no_audit, cache_mock):
    conn = fake_conn(
        monkeypatch,
        platform_admins,
        fetch_rows=[
            [
                {
                    "user_id": GRANTEE,
                    "granted_by": ACTOR,
                    "granted_at": datetime(2026, 9, 5, tzinfo=UTC),
                    "revoked_at": None,
                }
            ]
        ],
    )
    row = await platform_admins.grant_superadmin(GRANTEE, ACTOR)
    assert row["user_id"] == GRANTEE and row["revoked_at"] is None
    cache_mock.set_platform_admin.assert_awaited_once_with(GRANTEE, True)
    no_audit.assert_awaited_once()
    sqls = " ".join(_sqls(conn.fetchrow))
    assert "ON CONFLICT (user_id)" in sqls and "$1::uuid" in sqls


async def test_revoke_only_when_active(monkeypatch, no_audit, cache_mock):
    conn = fake_conn(monkeypatch, platform_admins, execute_results=["UPDATE 1"])
    assert await platform_admins.revoke_superadmin(GRANTEE, ACTOR) is True
    cache_mock.set_platform_admin.assert_awaited_once_with(GRANTEE, False)
    assert any("revoked_at IS NULL" in sql for sql in _sqls(conn.execute))

    fake_conn(monkeypatch, platform_admins, execute_results=["UPDATE 0"])
    cache_mock.set_platform_admin.reset_mock()
    assert await platform_admins.revoke_superadmin(GRANTEE, ACTOR) is False
    cache_mock.set_platform_admin.assert_not_awaited()


async def test_list_superadmins_marks_active(monkeypatch):
    fake_conn(
        monkeypatch,
        platform_admins,
        fetch_rows=[
            [
                {
                    "user_id": GRANTEE,
                    "granted_by": ACTOR,
                    "granted_at": datetime(2026, 9, 5, tzinfo=UTC),
                    "revoked_by": None,
                    "revoked_at": None,
                }
            ]
        ],
        fetch_vals=["root@example.com"],
    )
    admins = await platform_admins.list_superadmins()
    assert admins[0]["active"] is True
    assert admins[0]["email"] == "root@example.com"


# ---------------------------------------------------------------------------
# admin_audit
# ---------------------------------------------------------------------------


async def test_admin_audit_write_contract(monkeypatch):
    import app.services.admin_audit as audit_module

    conn = fake_conn(monkeypatch, audit_module)
    ok = await record_admin_action(ACTOR, "tenant.provision", "tenant", TENANT, {"name": "Acme"})
    assert ok is True
    call = conn.execute.call_args
    sql, args = call.args[0], call.args[1:]
    assert "INSERT INTO admin_audit" in sql and "$1::uuid" in sql
    assert args[0] == ACTOR and args[1] == "tenant.provision"
    assert json.loads(args[4]) == {"name": "Acme"}


async def test_admin_audit_fail_open(monkeypatch):
    import app.services.admin_audit as audit_module

    fake_conn(monkeypatch, audit_module, execute_results=[RuntimeError("audit down")])
    assert await record_admin_action(ACTOR, "x", "y") is False  # never raises


# ---------------------------------------------------------------------------
# provision
# ---------------------------------------------------------------------------


async def test_provision_transactional_inserts_and_bcrypt(monkeypatch, no_audit, cache_mock):
    conn = fake_conn(monkeypatch, tenants)
    result = await provision_tenant(
        "Acme Corp", "acme", "Root@Acme.example", "a-secure-password", ACTOR
    )
    assert result["slug"] == "acme" and result["status"] == "active"
    inserts = [c.args for c in conn.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert any("INSERT INTO tenants" in c[0] for c in inserts)
    user_call = next(c for c in inserts if "INSERT INTO users" in c[0])
    user_args = user_call[1:]  # inserts already unwraps .args to tuples
    assert user_args[2] == "root@acme.example"
    assert verify_password("a-secure-password", user_args[3])
    assert json.loads(user_args[4]) == ["admin", "user"]
    cache_mock.set_tenant_status.assert_awaited_once_with(result["tenant_id"], "active")
    no_audit.assert_awaited_once()


async def test_provision_unique_violations_map(monkeypatch, no_audit, cache_mock):
    import asyncpg

    fake_conn(monkeypatch, tenants, execute_results=[asyncpg.UniqueViolationError("dup tenant")])
    with pytest.raises(TenantExistsError):
        await provision_tenant("A", "a", "x@y.example", "password123", ACTOR)

    fake_conn(
        monkeypatch,
        tenants,
        execute_results=["INSERT 0 1", asyncpg.UniqueViolationError("dup user")],
    )
    with pytest.raises(UserExistsError):
        await provision_tenant("A", "a", "x@y.example", "password123", ACTOR)


# ---------------------------------------------------------------------------
# update / decommission
# ---------------------------------------------------------------------------


async def test_update_status_refreshes_cache(monkeypatch, no_audit, cache_mock):
    detail = {
        "id": TENANT,
        "name": "A",
        "slug": "a",
        "status": "suspended",
        "settings": {},
        "created_at": "2026-09-05T00:00:00+00:00",
        "updated_at": "2026-09-05T00:00:00+00:00",
        "user_count": 0,
        "users": [],
        "counters": {},
        "recent_admin_actions": [],
    }
    monkeypatch.setattr(tenants, "get_tenant", AsyncMock(return_value=detail))
    conn = fake_conn(
        monkeypatch,
        tenants,
        fetch_rows=[
            [
                {
                    "id": TENANT,
                    "name": "A",
                    "slug": "a",
                    "status": "active",
                    "settings": None,
                }
            ]
        ],
    )
    result = await update_tenant(TENANT, ACTOR, status="suspended")
    assert result["status"] == "suspended"
    cache_mock.set_tenant_status.assert_awaited_once_with(TENANT, "suspended")
    updates = [c.args[0] for c in conn.execute.call_args_list if "UPDATE tenants" in c.args[0]]
    assert any("status = $2" in sql for sql in updates)
    no_audit.assert_awaited_once()


async def test_decommission_refuses_non_empty(monkeypatch, no_audit, cache_mock):
    conn = fake_conn(monkeypatch, tenants, fetch_vals=[3, 1])  # 3 users, exists
    with pytest.raises(TenantNotEmptyError):
        await decommission_tenant(TENANT, ACTOR, force=False)
    # nothing deleted — only the guard queries ran
    assert all("DELETE" not in c.args[0] for c in conn.execute.call_args_list)


async def test_decommission_force_cleans_and_deletes(monkeypatch, no_audit, cache_mock):
    admin_conn = fake_conn(monkeypatch, tenants, fetch_vals=[0, 1])
    admin_conn.execute = AsyncMock(return_value="DELETE 1")

    owner_conn = MagicMock()
    owner_conn.close = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    owner_conn.transaction = MagicMock(return_value=tx)
    owner_conn.execute = AsyncMock(return_value="DELETE 1")

    async def fake_connect(dsn):
        # analytics cleanup connects as the owner (DATABASE_URL_SYNC)
        return owner_conn if "genbi:" in dsn else admin_conn

    monkeypatch.setattr(tenants.asyncpg, "connect", fake_connect)

    deleted = await decommission_tenant(TENANT, ACTOR, force=True)
    assert deleted is True

    owner_sqls = [c.args[0] for c in owner_conn.execute.call_args_list]
    assert any("set_config" in sql for sql in owner_sqls)
    assert any("DELETE FROM sales" in sql for sql in owner_sqls)
    assert any("DELETE FROM transactions" in sql for sql in owner_sqls)
    # tenant delete + cache poison on the admin conn
    assert any("DELETE FROM tenants" in c.args[0] for c in admin_conn.execute.call_args_list)
    cache_mock.set_tenant_status.assert_awaited_once_with(TENANT, "deleted")
    no_audit.assert_awaited_once()


async def test_decommission_missing_returns_false(monkeypatch, no_audit, cache_mock):
    fake_conn(monkeypatch, tenants, fetch_vals=[0, None])
    assert await decommission_tenant(TENANT, ACTOR, force=True) is False
