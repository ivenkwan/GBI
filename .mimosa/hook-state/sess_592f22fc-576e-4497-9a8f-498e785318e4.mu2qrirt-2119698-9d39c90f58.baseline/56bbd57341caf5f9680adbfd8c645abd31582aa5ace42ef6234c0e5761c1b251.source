"""Phase 24 API guard matrix for /wiki (service functions monkeypatched)."""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"

WIKI_HITS = [
    {"slug": "glossary", "title": "Glossary", "chunk": "qualified pipeline means", "score": 0.9}
]

SAMPLE_PAGE = {
    "slug": "glossary",
    "title": "Glossary",
    "content_md": "c",
    "parent_slug": None,
    "updated_by": USER,
    "updated_at": "2026-09-05T00:00:00+00:00",
    "created_at": "2026-09-05T00:00:00+00:00",
    "version": 1,
    "embedded": False,
}


@pytest_asyncio.fixture
async def api_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _headers(roles, platform_admin=False):
    token = create_access_token(
        user_id=USER, tenant_id=TENANT, roles=roles, platform_admin=platform_admin
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def lookups(monkeypatch):
    monkeypatch.setattr("app.core.auth._lookup_platform_admin", AsyncMock(return_value=True))
    monkeypatch.setattr("app.core.auth._lookup_tenant_status", AsyncMock(return_value="active"))


async def test_wiki_reads_for_any_user(api_client, monkeypatch):
    import app.services.wiki as wiki_module

    monkeypatch.setattr(wiki_module, "list_pages", AsyncMock(return_value=[]))
    res = await api_client.get("/api/v1/wiki", headers=_headers(["user"]))
    assert res.status_code == 200


async def test_wiki_write_requires_admin(api_client):
    body = {"title": "T", "content_md": "c"}
    res = await api_client.put("/api/v1/wiki/page", json=body, headers=_headers(["user"]))
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "WIKI_READ_ONLY"

    res = await api_client.delete("/api/v1/wiki/page", headers=_headers(["user"]))
    assert res.status_code == 403


async def test_wiki_write_admin_ok(api_client, monkeypatch):
    import app.services.wiki as wiki_module

    monkeypatch.setattr(wiki_module, "upsert_page", AsyncMock(return_value=SAMPLE_PAGE))
    res = await api_client.put(
        "/api/v1/wiki/glossary",
        json={"title": "Glossary", "content_md": "c"},
        headers=_headers(["admin", "user"]),
    )
    assert res.status_code == 200 and res.json()["slug"] == "glossary"


async def test_wiki_invalid_slug_and_not_found(api_client, monkeypatch):
    import app.services.wiki as wiki_module

    res = await api_client.get("/api/v1/wiki/Bad_Slug", headers=_headers(["user"]))
    assert res.status_code == 400 and res.json()["detail"]["code"] == "INVALID_SLUG"

    monkeypatch.setattr(wiki_module, "get_page", AsyncMock(return_value=None))
    res = await api_client.get("/api/v1/wiki/ghost", headers=_headers(["user"]))
    assert res.status_code == 404 and res.json()["detail"]["code"] == "PAGE_NOT_FOUND"

    monkeypatch.setattr(wiki_module, "page_history", AsyncMock(return_value=None))
    res = await api_client.get("/api/v1/wiki/ghost/history", headers=_headers(["user"]))
    assert res.status_code == 404


async def test_wiki_search_and_restore(api_client, monkeypatch):
    import app.services.wiki as wiki_module

    monkeypatch.setattr(wiki_module, "search_pages", AsyncMock(return_value=WIKI_HITS))
    res = await api_client.get("/api/v1/wiki/search?q=qualified", headers=_headers(["user"]))
    assert res.status_code == 200 and res.json()[0]["slug"] == "glossary"

    restored = {**SAMPLE_PAGE, "version": 3}
    monkeypatch.setattr(wiki_module, "restore_page", AsyncMock(return_value=restored))
    res = await api_client.post(
        "/api/v1/wiki/glossary/restore/1", headers=_headers(["admin", "user"])
    )
    assert res.status_code == 200 and res.json()["version"] == 3

    monkeypatch.setattr(wiki_module, "restore_page", AsyncMock(return_value=None))
    res = await api_client.post(
        "/api/v1/wiki/glossary/restore/99", headers=_headers(["admin", "user"])
    )
    assert res.status_code == 404 and res.json()["detail"]["code"] == "REVISION_NOT_FOUND"
