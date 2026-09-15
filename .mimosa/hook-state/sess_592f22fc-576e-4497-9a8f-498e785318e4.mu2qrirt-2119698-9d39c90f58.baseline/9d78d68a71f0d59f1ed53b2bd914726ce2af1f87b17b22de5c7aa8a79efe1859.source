"""Phase 23 API tests: /users guard matrix + /auth/me + change-password.

Service functions are monkeypatched (never assigned directly); guards and
error mapping are the unit under test. Test-only passwords are generated
at runtime — no credential literals in source.
"""

import secrets
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token, decode_token

TENANT = "00000000-0000-0000-0000-000000000001"
OTHER_TENANT = "00000000-0000-0000-0000-0000000000cc"
USER = "00000000-0000-0000-0000-0000000000aa"
TARGET = "00000000-0000-0000-0000-0000000000bb"

# Throwaway passwords for the request bodies only — never real credentials.
_PW = secrets.token_urlsafe(12)


@pytest_asyncio.fixture
async def api_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _token(roles, platform_admin=False, tenant=TENANT, email="who@example.com"):
    return create_access_token(
        user_id=USER, tenant_id=tenant, roles=roles, platform_admin=platform_admin, email=email
    )


@pytest.fixture(autouse=True)
def control_plane_lookups(monkeypatch):
    monkeypatch.setattr("app.core.auth._lookup_platform_admin", AsyncMock(return_value=True))
    monkeypatch.setattr("app.core.auth._lookup_tenant_status", AsyncMock(return_value="active"))


# ---------------------------------------------------------------------------
# Guard matrix
# ---------------------------------------------------------------------------


async def test_plain_user_forbidden(api_client, monkeypatch):
    import app.services.users as users_module

    monkeypatch.setattr(users_module, "list_users", AsyncMock(return_value=[]))
    res = await api_client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {_token(['user'])}"}
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "NOT_TENANT_ADMIN"


async def test_tenant_admin_allowed(api_client, monkeypatch):
    import app.services.users as users_module

    monkeypatch.setattr(
        users_module,
        "list_users",
        AsyncMock(
            return_value=[
                {
                    "id": TARGET,
                    "email": "t@example.com",
                    "roles": ["user"],
                    "status": "active",
                    "created_at": "2026-09-05T00:00:00+00:00",
                    "last_login_at": None,
                }
            ]
        ),
    )
    res = await api_client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"}
    )
    assert res.status_code == 200 and res.json()["count"] == 1


async def test_superuser_cross_tenant_allowed(api_client, monkeypatch):
    import app.services.users as users_module

    captured = {}

    async def fake_list(tenant_id):
        captured["tenant_id"] = tenant_id
        return []

    monkeypatch.setattr(users_module, "list_users", fake_list)
    res = await api_client.get(
        f"/api/v1/users?tenant_id={OTHER_TENANT}",
        headers={"Authorization": f"Bearer {_token(['user'], platform_admin=True)}"},
    )
    assert res.status_code == 200
    assert captured["tenant_id"] == OTHER_TENANT


async def test_plain_user_cannot_target_other_tenant(api_client, monkeypatch):
    import app.services.users as users_module

    monkeypatch.setattr(users_module, "list_users", AsyncMock(return_value=[]))
    res = await api_client.get(
        f"/api/v1/users?tenant_id={OTHER_TENANT}",
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "NOT_TENANT_ADMIN"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


async def test_create_conflict_and_invalid_roles(api_client, monkeypatch):
    import app.services.users as users_module
    from app.services.users import InvalidRolesError, UserExistsError

    async def boom(**kwargs):
        raise UserExistsError("dup")

    monkeypatch.setattr(users_module, "create_user", boom)
    res = await api_client.post(
        "/api/v1/users",
        json={"email": "x@y.example", "password": _PW},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 409 and res.json()["detail"]["code"] == "USER_EXISTS"

    async def bad_roles(**kwargs):
        raise InvalidRolesError("bad")

    monkeypatch.setattr(users_module, "create_user", bad_roles)
    res = await api_client.post(
        "/api/v1/users",
        json={"email": "x@y.example", "password": _PW, "roles": ["root"]},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 400 and res.json()["detail"]["code"] == "INVALID_ROLES"


async def test_update_last_admin_and_missing(api_client, monkeypatch):
    import app.services.users as users_module
    from app.services.users import LastTenantAdminError, UserNotFoundError

    async def last_admin(**kwargs):
        raise LastTenantAdminError("last admin")

    monkeypatch.setattr(users_module, "update_user", last_admin)
    res = await api_client.patch(
        f"/api/v1/users/{TARGET}",
        json={"status": "disabled"},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 422 and res.json()["detail"]["code"] == "LAST_TENANT_ADMIN"

    async def missing(**kwargs):
        raise UserNotFoundError("nope")

    monkeypatch.setattr(users_module, "update_user", missing)
    res = await api_client.patch(
        f"/api/v1/users/{TARGET}",
        json={"email": "new@example.com"},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 404

    monkeypatch.setattr(users_module, "update_user", AsyncMock(return_value=None))
    res = await api_client.patch(
        f"/api/v1/users/{TARGET}",
        json={"email": "new@example.com"},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 404 and res.json()["detail"]["code"] == "USER_NOT_FOUND"

    res = await api_client.patch(
        "/api/v1/users/not-a-uuid",
        json={"email": "new@example.com"},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 400


async def test_delete_and_reset_paths(api_client, monkeypatch):
    import app.services.users as users_module
    from app.services.users import LastTenantAdminError

    async def last_admin(**kwargs):
        raise LastTenantAdminError("last admin")

    monkeypatch.setattr(users_module, "delete_user", last_admin)
    res = await api_client.delete(
        f"/api/v1/users/{TARGET}",
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 422

    monkeypatch.setattr(users_module, "delete_user", AsyncMock(return_value=True))
    res = await api_client.delete(
        f"/api/v1/users/{TARGET}",
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 200

    monkeypatch.setattr(users_module, "reset_password", AsyncMock(return_value=False))
    res = await api_client.post(
        f"/api/v1/users/{TARGET}/reset-password",
        json={"password": _PW},
        headers={"Authorization": f"Bearer {_token(['admin', 'user'])}"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# /auth/me + /auth/change-password
# ---------------------------------------------------------------------------


async def test_whoami_fidelity(api_client):
    token = _token(["admin", "user"], platform_admin=True, email="admin@x.example")
    res = await api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    body = res.json()
    assert res.status_code == 200
    assert body["email"] == "admin@x.example"
    assert body["platform_admin"] is True
    assert body["roles"] == ["admin", "user"]
    assert body["tenant_id"] == TENANT

    plain = _token(["user"], platform_admin=False, email="u@x.example")
    res = await api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {plain}"})
    assert res.json()["platform_admin"] is False


async def test_change_password_mapping(api_client, monkeypatch):
    import app.services.users as users_module

    monkeypatch.setattr(users_module, "change_password", AsyncMock(return_value=False))
    res = await api_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": _PW, "new_password": secrets.token_urlsafe(12)},
        headers={"Authorization": f"Bearer {_token(['user'])}"},
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "INVALID_CREDENTIALS"

    monkeypatch.setattr(users_module, "change_password", AsyncMock(return_value=True))
    res = await api_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": _PW, "new_password": secrets.token_urlsafe(12)},
        headers={"Authorization": f"Bearer {_token(['user'])}"},
    )
    assert res.status_code == 200


def test_email_claim_in_token():
    token = create_access_token(USER, TENANT, ["user"], email="claim@x.example")
    assert decode_token(token)["email"] == "claim@x.example"
    assert decode_token(create_access_token(USER, TENANT, ["user"])).get("email") is None
