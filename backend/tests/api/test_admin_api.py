"""Phase 21 admin API tests: guard semantics, endpoint matrix, auth claims.

All service functions are monkeypatched (never assigned directly — leaked
mocks break later test files). Auth-claim behavior (platform_admin minting,
suspension enforcement, revocation re-check) is covered here too. Test
passwords are generated at runtime — no credential literals in source.
"""

import secrets
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token, decode_token

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
GRANTEE = "00000000-0000-0000-0000-0000000000bb"
OTHER = "00000000-0000-0000-0000-0000000000cc"


@pytest_asyncio.fixture
async def api_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _headers(platform_admin: bool) -> dict:
    token = create_access_token(
        user_id=USER, tenant_id=TENANT, roles=["admin", "user"], platform_admin=platform_admin
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superuser_headers():
    return _headers(platform_admin=True)


@pytest.fixture
def user_headers():
    return _headers(platform_admin=False)


@pytest.fixture(autouse=True)
def grants_active(monkeypatch):
    """DB-fallback lookups patched out; the real cache carries the state.

    These tests exercise the CACHED enforcement semantics (the ≤60s
    revocation/suspension window) against the real cache service —
    Redis/local L1 — exactly as production reads it. Seeding happens in
    the async ``seed_grants`` fixture below.
    """
    monkeypatch.setattr("app.core.auth._lookup_platform_admin", AsyncMock(return_value=True))
    monkeypatch.setattr("app.core.auth._lookup_tenant_status", AsyncMock(return_value="active"))
    return None


@pytest.fixture(autouse=True)
async def seed_grants():
    """Seed the passing state before each test and restore it after —
    keeps the shared cache sane for later test files."""
    from app.core.cache import get_cache

    await get_cache().set_platform_admin(USER, True)
    await get_cache().set_tenant_status(TENANT, "active")
    yield
    await get_cache().set_platform_admin(USER, True)
    await get_cache().set_tenant_status(TENANT, "active")


# ---------------------------------------------------------------------------
# Guard semantics
# ---------------------------------------------------------------------------


async def test_admin_requires_platform_admin_claim(api_client, user_headers):
    res = await api_client.get("/api/v1/admin/stats", headers=user_headers)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "NOT_PLATFORM_ADMIN"


async def test_revoked_superuser_rejected_within_cache_window(api_client, superuser_headers):
    # Claim present, but the cached grant-table re-check says revoked —
    # the ≤60s revocation window semantics, exercised on the real cache.
    from app.core.cache import get_cache

    await get_cache().set_platform_admin(USER, False)
    res = await api_client.get("/api/v1/admin/stats", headers=superuser_headers)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "NOT_PLATFORM_ADMIN"


async def test_grant_lookup_fails_open(api_client, superuser_headers, monkeypatch):
    # Cache AND DB both unavailable on the re-check: the claim (minted at
    # login from the same table) still admits — the guard fails open.
    monkeypatch.setattr(
        "app.core.auth._lookup_platform_admin", AsyncMock(side_effect=RuntimeError("db down"))
    )

    class ExplodingCache:
        async def get_platform_admin(self, user_id):
            raise RuntimeError("cache down")

        async def set_platform_admin(self, user_id, value):
            raise RuntimeError("cache down")

    monkeypatch.setattr("app.core.cache.get_cache", lambda: ExplodingCache())

    import app.services.tenants as tenants_module

    monkeypatch.setattr(
        tenants_module,
        "platform_stats",
        AsyncMock(
            return_value={
                "tenants_total": 1,
                "tenants_active": 1,
                "tenants_suspended": 0,
                "users_total": 1,
                "llm_calls_24h": 0,
                "platform_admins_active": 1,
            }
        ),
    )
    res = await api_client.get("/api/v1/admin/stats", headers=superuser_headers)
    assert res.status_code == 200


async def test_suspended_tenant_rejected_on_ordinary_endpoint(api_client, user_headers):
    # Cached suspension on the real cache — the ≤60s enforcement window.
    from app.core.cache import get_cache

    await get_cache().set_tenant_status(TENANT, "suspended")
    res = await api_client.get("/api/v1/metrics/list", headers=user_headers)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "TENANT_SUSPENDED"


async def test_unknown_tenant_status_fails_open(api_client, user_headers):
    # /conversations hits the DB (not mocked) — but the 403-under-test must
    # NOT appear; any other status (including 503) proves fail-open.
    res = await api_client.get("/api/v1/conversations", headers=user_headers)
    assert res.status_code != 403


# ---------------------------------------------------------------------------
# JWT claim fidelity
# ---------------------------------------------------------------------------


def test_platform_admin_claim_roundtrip():
    token = create_access_token(user_id=USER, tenant_id=TENANT, roles=["user"], platform_admin=True)
    assert decode_token(token)["platform_admin"] is True

    plain = create_access_token(user_id=USER, tenant_id=TENANT, roles=["user"])
    assert decode_token(plain)["platform_admin"] is False


# ---------------------------------------------------------------------------
# Tenant endpoints
# ---------------------------------------------------------------------------


async def test_stats(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_module

    monkeypatch.setattr(
        tenants_module,
        "platform_stats",
        AsyncMock(
            return_value={
                "tenants_total": 3,
                "tenants_active": 2,
                "tenants_suspended": 1,
                "users_total": 7,
                "llm_calls_24h": 42,
                "platform_admins_active": 2,
            }
        ),
    )
    res = await api_client.get("/api/v1/admin/stats", headers=superuser_headers)
    assert res.status_code == 200 and res.json()["tenants_total"] == 3


async def test_list_tenants(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_module

    monkeypatch.setattr(
        tenants_module,
        "list_tenants",
        AsyncMock(
            return_value=[
                {
                    "id": TENANT,
                    "name": "Acme",
                    "slug": "acme",
                    "status": "active",
                    "created_at": "2026-09-05T00:00:00+00:00",
                    "user_count": 2,
                }
            ]
        ),
    )
    res = await api_client.get("/api/v1/admin/tenants", headers=superuser_headers)
    assert res.status_code == 200 and res.json()["count"] == 1


async def test_provision_generates_password_once(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_module

    captured = {}

    async def fake_provision(**kwargs):
        captured.update(kwargs)
        return {
            "tenant_id": OTHER,
            "name": kwargs["name"],
            "slug": kwargs["slug"],
            "status": "active",
            "admin_user_id": GRANTEE,
            "admin_email": kwargs["admin_email"],
            "seeded": kwargs["seed_sample_data"],
            "created_at": "2026-09-05T00:00:00+00:00",
        }

    monkeypatch.setattr(tenants_module, "provision_tenant", fake_provision)
    res = await api_client.post(
        "/api/v1/admin/tenants",
        json={"name": "Acme", "slug": "acme", "admin_email": "root@acme.example"},
        headers=superuser_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["temp_password"] and len(body["temp_password"]) >= 12
    # generated password flowed into the service (and is never stored)
    assert captured["admin_password"] == body["temp_password"]
    assert captured["actor_user_id"] == USER

    # explicit password (runtime-generated — no literal credentials in
    # source) → never echoed back
    explicit_pw = secrets.token_urlsafe(12)
    res = await api_client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Acme",
            "slug": "acme2",
            "admin_email": "r2@acme.example",
            "admin_password": explicit_pw,
        },
        headers=superuser_headers,
    )
    assert res.status_code == 201 and res.json()["temp_password"] is None


async def test_provision_validation_errors(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_module
    from app.services.tenants import TenantExistsError, UserExistsError

    async def boom(**kwargs):
        raise TenantExistsError("slug in use")

    monkeypatch.setattr(tenants_module, "provision_tenant", boom)
    res = await api_client.post(
        "/api/v1/admin/tenants",
        json={"name": "A", "slug": "acme", "admin_email": "r@acme.example"},
        headers=superuser_headers,
    )
    assert res.status_code == 409 and res.json()["detail"]["code"] == "TENANT_EXISTS"

    async def boom_user(**kwargs):
        raise UserExistsError("user exists")

    monkeypatch.setattr(tenants_module, "provision_tenant", boom_user)
    res = await api_client.post(
        "/api/v1/admin/tenants",
        json={"name": "A", "slug": "acme", "admin_email": "r@acme.example"},
        headers=superuser_headers,
    )
    assert res.status_code == 409 and res.json()["detail"]["code"] == "USER_EXISTS"

    res = await api_client.post(
        "/api/v1/admin/tenants",
        json={"name": "A", "slug": "Bad Slug!", "admin_email": "r@acme.example"},
        headers=superuser_headers,
    )
    assert res.status_code == 400 and res.json()["detail"]["code"] == "INVALID_SLUG"

    res = await api_client.post(
        "/api/v1/admin/tenants",
        json={"name": "A", "slug": "acme", "admin_email": "not-an-email"},
        headers=superuser_headers,
    )
    assert res.status_code == 400 and res.json()["detail"]["code"] == "INVALID_EMAIL"


async def test_get_and_patch_tenant(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_module

    detail = {
        "id": TENANT,
        "name": "Acme",
        "slug": "acme",
        "status": "active",
        "settings": {},
        "created_at": "2026-09-05T00:00:00+00:00",
        "updated_at": "2026-09-05T00:00:00+00:00",
        "user_count": 1,
        "users": [],
        "counters": {"reports": 0},
        "recent_admin_actions": [],
    }
    monkeypatch.setattr(tenants_module, "get_tenant", AsyncMock(return_value=detail))
    monkeypatch.setattr(
        tenants_module,
        "update_tenant",
        AsyncMock(return_value={**detail, "status": "suspended"}),
    )

    res = await api_client.get(f"/api/v1/admin/tenants/{TENANT}", headers=superuser_headers)
    assert res.status_code == 200 and res.json()["id"] == TENANT

    res = await api_client.patch(
        f"/api/v1/admin/tenants/{TENANT}",
        json={"status": "suspended"},
        headers=superuser_headers,
    )
    assert res.status_code == 200 and res.json()["status"] == "suspended"

    monkeypatch.setattr(tenants_module, "get_tenant", AsyncMock(return_value=None))
    res = await api_client.get(f"/api/v1/admin/tenants/{TENANT}", headers=superuser_headers)
    assert res.status_code == 404 and res.json()["detail"]["code"] == "TENANT_NOT_FOUND"

    res = await api_client.get("/api/v1/admin/tenants/nope", headers=superuser_headers)
    assert res.status_code == 400


async def test_decommission_guards(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_module
    from app.services.tenants import TenantNotEmptyError

    res = await api_client.delete(f"/api/v1/admin/tenants/{TENANT}", headers=superuser_headers)
    assert res.status_code == 400 and res.json()["detail"]["code"] == "CONFIRM_REQUIRED"

    async def not_empty(**kwargs):
        raise TenantNotEmptyError("3 users")

    monkeypatch.setattr(tenants_module, "decommission_tenant", not_empty)
    res = await api_client.delete(
        f"/api/v1/admin/tenants/{TENANT}?confirm=yes", headers=superuser_headers
    )
    assert res.status_code == 422 and res.json()["detail"]["code"] == "TENANT_NOT_EMPTY"

    monkeypatch.setattr(tenants_module, "decommission_tenant", AsyncMock(return_value=True))
    res = await api_client.delete(
        f"/api/v1/admin/tenants/{TENANT}?confirm=yes&force=true", headers=superuser_headers
    )
    assert res.status_code == 200

    monkeypatch.setattr(tenants_module, "decommission_tenant", AsyncMock(return_value=False))
    res = await api_client.delete(
        f"/api/v1/admin/tenants/{TENANT}?confirm=yes", headers=superuser_headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Superuser grant management + audit feed
# ---------------------------------------------------------------------------


async def test_admins_grant_revoke_list(api_client, superuser_headers, monkeypatch):
    import app.services.platform_admins as pa

    monkeypatch.setattr(
        pa,
        "grant_superadmin",
        AsyncMock(
            return_value={
                "user_id": GRANTEE,
                "granted_by": USER,
                "granted_at": "2026-09-05T00:00:00+00:00",
                "revoked_at": None,
            }
        ),
    )
    monkeypatch.setattr(pa, "revoke_superadmin", AsyncMock(return_value=True))
    monkeypatch.setattr(
        pa,
        "list_superadmins",
        AsyncMock(
            return_value=[
                {
                    "user_id": GRANTEE,
                    "email": "root@example.com",
                    "granted_by": USER,
                    "granted_at": "2026-09-05T00:00:00+00:00",
                    "revoked_by": None,
                    "revoked_at": None,
                    "active": True,
                }
            ]
        ),
    )

    res = await api_client.post(
        "/api/v1/admin/admins", json={"user_id": GRANTEE}, headers=superuser_headers
    )
    assert res.status_code == 201 and res.json()["active"] is True

    res = await api_client.get("/api/v1/admin/admins", headers=superuser_headers)
    assert res.status_code == 200 and res.json()[0]["user_id"] == GRANTEE

    res = await api_client.delete(f"/api/v1/admin/admins/{GRANTEE}", headers=superuser_headers)
    assert res.status_code == 200

    monkeypatch.setattr(pa, "revoke_superadmin", AsyncMock(return_value=False))
    res = await api_client.delete(f"/api/v1/admin/admins/{GRANTEE}", headers=superuser_headers)
    assert res.status_code == 404 and res.json()["detail"]["code"] == "GRANT_NOT_FOUND"


async def test_admins_grant_by_unknown_email_404(api_client, superuser_headers, monkeypatch):
    import app.api.v1.admin as admin_module

    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.close = AsyncMock()

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(admin_module.asyncpg, "connect", fake_connect)
    res = await api_client.post(
        "/api/v1/admin/admins", json={"email": "ghost@example.com"}, headers=superuser_headers
    )
    assert res.status_code == 404 and res.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_admin_audit_feed(api_client, superuser_headers, monkeypatch):
    import json as jsonlib

    import app.api.v1.admin as admin_module

    conn = MagicMock()
    conn.close = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "actor_user_id": uuid.UUID(USER),
                "action": "tenant.provision",
                "target_type": "tenant",
                "target_id": OTHER,
                "detail": jsonlib.dumps({"name": "Acme"}),
                "created_at": datetime(2026, 9, 5, tzinfo=UTC),
            }
        ]
    )

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(admin_module.asyncpg, "connect", fake_connect)
    res = await api_client.get("/api/v1/admin/audit", headers=superuser_headers)
    assert res.status_code == 200
    assert res.json()[0]["action"] == "tenant.provision"
    assert res.json()[0]["detail"] == {"name": "Acme"}
