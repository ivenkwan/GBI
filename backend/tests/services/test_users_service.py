"""Phase 23 user-service tests — all DB access faked (offline, CI-safe)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import hash_password, verify_password
from app.services import users as svc
from app.services.users import (
    InvalidRolesError,
    LastTenantAdminError,
    UserExistsError,
    change_password,
    create_user,
    delete_user,
    update_user,
)

TENANT = "00000000-0000-0000-0000-000000000001"
ACTOR = "00000000-0000-0000-0000-0000000000aa"
TARGET = "00000000-0000-0000-0000-0000000000bb"


def fake_conn(monkeypatch, module, *, fetch_rows=None, fetch_vals=None, execute_results=None):
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
        # Skip scripted results for the connection-setup GUC statement.
        if "set_config" in sql:
            return "SET"
        if execute_results:
            out = execute_results.pop(0)
            if isinstance(out, Exception):
                raise out
            return out
        return "UPDATE 1"

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
    monkeypatch.setattr(svc, "record_admin_action", mock)
    return mock


@pytest.fixture
def cache_mock(monkeypatch):
    cache = MagicMock()
    cache.register_failed_login = AsyncMock()
    monkeypatch.setattr(svc, "get_cache", lambda: cache)
    return cache


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_user_bcrypt_and_guc(monkeypatch, no_audit):
    conn = fake_conn(monkeypatch, svc)
    created = await create_user(
        TENANT, "Root@Example.COM", "a-secure-pass", ["admin", "user"], ACTOR
    )
    assert created["email"] == "root@example.com"  # normalized
    call = conn.execute.call_args
    sql, args = call.args[0], call.args[1:]
    assert "INSERT INTO users" in sql and "$2::uuid" in sql and "'active'" in sql
    assert args[1] == TENANT and args[2] == "root@example.com"
    assert verify_password("a-secure-pass", args[3])
    assert json.loads(args[4]) == ["admin", "user"]
    # tenant GUC set on the connection
    guc = conn.execute.call_args_list[0]
    assert "set_config" in guc.args[0] and guc.args[1] == TENANT
    no_audit.assert_awaited_once()


async def test_create_user_rejects_bad_roles(monkeypatch, no_audit):
    fake_conn(monkeypatch, svc)
    with pytest.raises(InvalidRolesError):
        await create_user(TENANT, "x@y.example", "password123", ["superadmin"], ACTOR)


async def test_create_user_duplicate_maps(monkeypatch, no_audit):
    import asyncpg

    fake_conn(monkeypatch, svc, execute_results=[asyncpg.UniqueViolationError("dup")])
    with pytest.raises(UserExistsError):
        await create_user(TENANT, "x@y.example", "password123", ["user"], ACTOR)


# ---------------------------------------------------------------------------
# update + last-admin guard
# ---------------------------------------------------------------------------


def _existing_row(roles, status="active"):
    return {
        "id": TARGET,
        "email": "target@example.com",
        "roles": json.dumps(roles),
        "status": status,
    }


def _final_row():
    return {
        "id": TARGET,
        "email": "target@example.com",
        "roles": json.dumps(["user"]),
        "status": "active",
        "created_at": __import__("datetime").datetime(
            2026, 9, 5, tzinfo=__import__("datetime").UTC
        ),
        "last_login_at": None,
    }


async def test_update_demote_last_admin_refused(monkeypatch, no_audit):
    conn = fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[[_existing_row(["admin", "user"])]],
        fetch_vals=[0],  # no other active admins
    )
    with pytest.raises(LastTenantAdminError):
        await update_user(TENANT, TARGET, ACTOR, roles=["user"])
    assert all("UPDATE users SET" not in c.args[0] for c in conn.execute.call_args_list)


async def test_update_demote_allowed_with_other_admin(monkeypatch, no_audit):
    fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[
            [_existing_row(["admin", "user"])],
            [_final_row()],  # re-fetch after updates
        ],
        fetch_vals=[1],  # one other active admin
    )
    result = await update_user(TENANT, TARGET, ACTOR, roles=["user"])
    assert result["roles"] == ["user"]
    no_audit.assert_awaited_once()


async def test_update_disable_last_admin_refused(monkeypatch, no_audit):
    fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[[_existing_row(["admin", "user"])]],
        fetch_vals=[0],
    )
    with pytest.raises(LastTenantAdminError):
        await update_user(TENANT, TARGET, ACTOR, status="disabled")


async def test_update_missing_user_returns_none(monkeypatch, no_audit):
    fake_conn(monkeypatch, svc, fetch_rows=[[]])
    assert await update_user(TENANT, TARGET, ACTOR, email="new@example.com") is None


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_last_admin_refused(monkeypatch, no_audit):
    conn = fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[[_existing_row(["admin", "user"])]],
        fetch_vals=[0],
    )
    with pytest.raises(LastTenantAdminError):
        await delete_user(TENANT, TARGET, ACTOR)
    assert all("DELETE FROM users" not in c.args[0] for c in conn.execute.call_args_list)


async def test_delete_non_admin(monkeypatch, no_audit):
    conn = fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[[_existing_row(["user"])]],
        execute_results=["DELETE 1"],
    )
    assert await delete_user(TENANT, TARGET, ACTOR) is True
    assert any("DELETE FROM users" in c.args[0] for c in conn.execute.call_args_list)


async def test_delete_missing_returns_false(monkeypatch, no_audit):
    fake_conn(monkeypatch, svc, fetch_rows=[[]])
    assert await delete_user(TENANT, TARGET, ACTOR) is False


# ---------------------------------------------------------------------------
# change_password
# ---------------------------------------------------------------------------


async def test_change_password_wrong_current_throttles(monkeypatch, cache_mock):
    fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[
            [
                {
                    "email": "target@example.com",
                    "hashed_password": hash_password("the-real-one"),
                }
            ]
        ],
    )
    changed = await change_password(TENANT, TARGET, "wrong", "new-password-1")
    assert changed is False
    cache_mock.register_failed_login.assert_awaited_once_with("target@example.com")


async def test_change_password_success(monkeypatch, cache_mock):
    conn = fake_conn(
        monkeypatch,
        svc,
        fetch_rows=[
            [
                {
                    "email": "target@example.com",
                    "hashed_password": hash_password("the-real-one"),
                }
            ]
        ],
    )
    changed = await change_password(TENANT, TARGET, "the-real-one", "new-password-1")
    assert changed is True
    update = next(c for c in conn.execute.call_args_list if "hashed_password = $3" in c.args[0])
    assert verify_password("new-password-1", update.args[3])
    cache_mock.register_failed_login.assert_not_awaited()


async def test_change_password_unknown_user_false(monkeypatch, cache_mock):
    fake_conn(monkeypatch, svc, fetch_rows=[[]])
    assert await change_password(TENANT, TARGET, "x", "new-password-1") is False
