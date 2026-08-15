"""Tests for the Phase 12 audit writer (app.services.audit)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.services import audit as audit_module
from app.services.audit import write_audit_entry

SESSION = str(uuid.uuid4())
USER = str(uuid.uuid4())
TENANT = "00000000-0000-0000-0000-000000000001"


def _entry(**overrides) -> dict:
    entry = {
        "session_id": SESSION,
        "user_id": USER,
        "tenant_id": TENANT,
        "input_prompt_hash": "a" * 64,
        "generated_sql": "SELECT 1",
        "model_name": "claude-opus-4",
        "model_version": "latest",
        "input_tokens": 100,
        "output_tokens": 50,
        "latency_ms": 12.5,
    }
    entry.update(overrides)
    return entry


def _make_conn() -> MagicMock:
    conn = MagicMock()
    conn.execute = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    conn.close = AsyncMock()
    return conn


def _patch_asyncpg(monkeypatch, conn=None, error=None):
    async def fake_connect(dsn=None, **kwargs):
        if error:
            raise error
        return conn

    monkeypatch.setattr(audit_module.asyncpg, "connect", fake_connect)
    return conn


async def test_write_sets_guc_then_inserts(monkeypatch):
    conn = _make_conn()
    _patch_asyncpg(monkeypatch, conn=conn)

    await write_audit_entry(_entry())

    assert conn.execute.await_count == 2

    # First call: the tenant GUC — statement plus one bound parameter
    guc_call = conn.execute.call_args_list[0]
    assert guc_call.args[1] == TENANT

    # Second call: the module's exact parameterized insert, fully bound
    insert_call = conn.execute.call_args_list[1]
    assert insert_call.args[0] == audit_module._AUDIT_INSERT
    assert insert_call.args[1:] == (
        SESSION,
        USER,
        TENANT,
        "a" * 64,
        "SELECT 1",
        "claude-opus-4",
        "latest",
        100,
        50,
        12.5,
    )


async def test_skips_non_uuid_identities(monkeypatch):
    conn = _make_conn()
    _patch_asyncpg(monkeypatch, conn=conn)

    await write_audit_entry(_entry(user_id="unknown", tenant_id="default"))

    assert conn.execute.await_count == 0, "no DB work for non-UUID identity fallbacks"


async def test_fails_open_on_db_error(monkeypatch):
    _patch_asyncpg(monkeypatch, error=ConnectionError("db down"))

    # Must not raise — an audit outage never breaks the pipeline
    await write_audit_entry(_entry())


async def test_hash_is_real_prompt_hash():
    """The llm_client callback now hashes the prompt text, not model+tokens."""
    import hashlib

    from app.core.llm_client import LLMCallResult, LLMClient

    captured: list[dict] = []

    async def callback(entry):
        captured.append(entry)

    client = LLMClient()
    client.set_audit_callback(callback)
    result = LLMCallResult(
        content="{}", model_name="claude-opus-4", input_tokens=10, output_tokens=5, latency_ms=1.0
    )

    await client._audit(
        result=result,
        messages="Show revenue by region",
        user_id=USER,
        tenant_id=TENANT,
        session_id=SESSION,
    )

    assert captured[0]["input_prompt_hash"] == hashlib.sha256(b"Show revenue by region").hexdigest()
    assert captured[0]["user_id"] == USER
    assert captured[0]["generated_sql"] == ""
