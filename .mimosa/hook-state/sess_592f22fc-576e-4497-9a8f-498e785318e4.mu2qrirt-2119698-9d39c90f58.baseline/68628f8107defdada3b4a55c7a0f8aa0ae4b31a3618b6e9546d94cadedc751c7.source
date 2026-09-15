"""API tests for /conversations (Phase 14) — service mocked, JWTs minted."""

from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token

TENANT = "00000000-0000-0000-0000-000000000001"
CONV = "00000000-0000-0000-0000-0000000000bb"


def _patch_service(monkeypatch, conversations=None, messages=None):
    """Patch the functions on the real conversations service module."""
    import app.services.conversations as svc

    fake = MagicMock()
    fake.list_conversations = AsyncMock(
        return_value=conversations
        if conversations is not None
        else [
            {
                "id": CONV,
                "title": "Q3 revenue",
                "created_at": "2026-08-15T10:00:00+00:00",
                "updated_at": "2026-08-15T10:05:00+00:00",
            }
        ]
    )
    fake.list_messages = AsyncMock(
        return_value=messages
        if messages is not None
        else [
            {
                "role": "user",
                "content": "revenue by region",
                "generated_sql": None,
                "created_at": "2026-08-15T10:00:00+00:00",
            }
        ]
    )
    monkeypatch.setattr(svc, "list_conversations", fake.list_conversations)
    monkeypatch.setattr(svc, "list_messages", fake.list_messages)
    return fake


async def _client() -> AsyncClient:
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    return AsyncClient(transport=transport, base_url="http://test")


def _auth_headers() -> dict:
    token = create_access_token(user_id="test-user", tenant_id=TENANT)
    return {"Authorization": f"Bearer {token}"}


async def test_list_conversations_returns_summaries(monkeypatch):
    fake = _patch_service(monkeypatch)

    async with await _client() as client:
        res = await client.get("/api/v1/conversations", headers=_auth_headers())

    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["conversations"][0]["title"] == "Q3 revenue"
    fake.list_conversations.assert_awaited_once()


async def test_list_messages_returns_turns(monkeypatch):
    fake = _patch_service(monkeypatch)

    async with await _client() as client:
        res = await client.get(f"/api/v1/conversations/{CONV}/messages", headers=_auth_headers())

    assert res.status_code == 200
    body = res.json()
    assert body["messages"][0]["role"] == "user"
    fake.list_messages.assert_awaited_once_with(conversation_id=CONV, tenant_id=TENANT, limit=50)


async def test_list_messages_rejects_non_uuid(monkeypatch):
    _patch_service(monkeypatch)

    async with await _client() as client:
        res = await client.get("/api/v1/conversations/not-a-uuid/messages", headers=_auth_headers())

    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_CONVERSATION"


async def test_list_conversations_503_when_store_down(monkeypatch):
    import app.services.conversations as svc

    _patch_service(monkeypatch)
    monkeypatch.setattr(
        svc, "list_conversations", AsyncMock(side_effect=ConnectionError("db down"))
    )

    async with await _client() as client:
        res = await client.get("/api/v1/conversations", headers=_auth_headers())

    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "PERSISTENCE_UNAVAILABLE"


async def test_requires_auth(monkeypatch):
    _patch_service(monkeypatch)

    async with await _client() as client:
        res = await client.get("/api/v1/conversations")

    assert res.status_code in (401, 403)
