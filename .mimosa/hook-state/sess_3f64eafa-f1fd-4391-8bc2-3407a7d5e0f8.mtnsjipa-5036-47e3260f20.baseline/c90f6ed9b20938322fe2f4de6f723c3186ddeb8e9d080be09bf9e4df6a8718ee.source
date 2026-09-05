"""Tests for the conversations service (Phase 14) — mocked asyncpg.

Pins the persistence contract: tenant GUC before every statement,
parameterized reads/writes, per-user scoping, fail-open writes,
raise-on-read (callers decide degradation).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.services import conversations as svc

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
CONV = "00000000-0000-0000-0000-0000000000bb"
NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _patch_connect(monkeypatch, fetch_rows=None, error=None):
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=fetch_rows or [],
        side_effect=error if error else None,
    )
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    async def fake_connect(dsn=None, **kwargs):
        return conn

    monkeypatch.setattr(svc.asyncpg, "connect", fake_connect)
    return conn


async def test_create_conversation_sets_guc_then_inserts(monkeypatch):
    conn = _patch_connect(monkeypatch)

    created = await svc.create_conversation(USER, TENANT, title="revenue question")

    assert created is not None
    guc_call = conn.execute.call_args_list[0]
    assert guc_call.args[1] == TENANT
    insert_call = conn.execute.call_args_list[1]
    assert insert_call.args[0].startswith("INSERT INTO conversations")
    assert insert_call.args[1:] == (created, USER, TENANT, "revenue question")


async def test_create_conversation_fail_open(monkeypatch):
    conn = _patch_connect(monkeypatch)
    conn.execute = AsyncMock(side_effect=ConnectionError("db down"))

    assert await svc.create_conversation(USER, TENANT, title="t") is None


async def test_append_message_inserts_and_bumps_updated_at(monkeypatch):
    conn = _patch_connect(monkeypatch)

    await svc.append_message(CONV, TENANT, "user", "hello", generated_sql="SELECT 1")

    # GUC, INSERT, UPDATE — in order, inside the transaction
    statements = [c.args[0] for c in conn.execute.call_args_list]
    assert len(statements) == 3
    assert statements[1].startswith("INSERT INTO messages")
    assert statements[2].startswith("UPDATE conversations")
    assert conn.execute.call_args_list[1].args[1:] == (CONV, TENANT, "user", "hello", "SELECT 1")


async def test_append_message_fail_open(monkeypatch):
    conn = _patch_connect(monkeypatch)
    conn.execute = AsyncMock(side_effect=RuntimeError("gone"))

    # Must not raise
    await svc.append_message(CONV, TENANT, "assistant", "text")


async def test_list_conversations_scopes_to_user(monkeypatch):
    conn = _patch_connect(
        monkeypatch,
        fetch_rows=[{"id": CONV, "title": "Q3 revenue", "created_at": NOW, "updated_at": NOW}],
    )

    rows = await svc.list_conversations(USER, TENANT, limit=10)

    fetch_call = conn.fetch.call_args
    assert fetch_call.args[1] == USER  # user scoping parameter
    assert fetch_call.args[2] == 10
    assert rows[0]["id"] == CONV
    assert rows[0]["title"] == "Q3 revenue"


async def test_list_messages_reverses_to_chronological(monkeypatch):
    def row(role, content, i):
        return {
            "role": role,
            "content": content,
            "generated_sql": None,
            "created_at": NOW.replace(minute=i),
        }

    # DB returns newest-first; the service must return chronological
    conn = _patch_connect(
        monkeypatch,
        fetch_rows=[row("assistant", "answer", 1), row("user", "question", 0)],
    )

    rows = await svc.list_messages(CONV, TENANT)

    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert conn.fetch.call_args.args[1] == CONV


async def test_list_messages_raises_on_db_error(monkeypatch):
    _patch_connect(monkeypatch, error=ConnectionError("db down"))

    import pytest

    with pytest.raises(ConnectionError):
        await svc.list_messages(CONV, TENANT)
