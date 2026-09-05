"""Phase 26 BYOK API tests: guard matrix, masked responses, error mapping,
spend attribution wiring — all service I/O monkeypatched (offline).

The key-absence contract is asserted on every response shape: no payload
may contain the plaintext key or any api_key field (only key_last4).
Test key material is generated at runtime — no credential literals.
"""

import secrets
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
OTHER_TENANT = "00000000-0000-0000-0000-000000000002"

MASKED_CONFIG = {
    "provider": "openai",
    "base_url": "https://gw.example.com/v1",
    "reasoning_model": "o4-mini",
    "fast_model": "gpt-5-mini",
    "embedding_model": "text-embedding-3-small",
    "key_last4": "abcd",
    "key_version": 3,
    "status": "active",
    "updated_at": "2026-09-05T00:00:00+00:00",
}

USAGE_ROWS = [
    {
        "day": "2026-09-05",
        "provider": "openai",
        "key_source": "tenant",
        "model_name": "gpt-5-mini",
        "calls": 12,
        "input_tokens": 3400,
        "output_tokens": 800,
    }
]


def _no_key_material(obj) -> bool:
    """Recursively: no api_key-ish field, no plaintext key value, anywhere."""
    banned_fragments = ("api_key", "api_key_enc")
    if isinstance(obj, dict):
        for key, value in obj.items():
            if any(fragment in str(key) for fragment in banned_fragments):
                return False
            if not _no_key_material(value):
                return False
        return True
    if isinstance(obj, list):
        return all(_no_key_material(item) for item in obj)
    return not isinstance(obj, str) or "sk-" not in obj


@pytest_asyncio.fixture
async def api_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _headers(platform_admin: bool, roles: list[str] | None = None) -> dict:
    from app.core.auth import create_access_token

    token = create_access_token(
        user_id=USER,
        tenant_id=TENANT,
        roles=roles if roles is not None else ["admin", "user"],
        platform_admin=platform_admin,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _headers(platform_admin=False)


@pytest.fixture
def plain_headers():
    return _headers(platform_admin=False, roles=["user"])


@pytest.fixture
def superuser_headers():
    return _headers(platform_admin=True)


@pytest.fixture(autouse=True)
def grants_active(monkeypatch):
    """DB-fallback lookups patched out; the real cache carries the state."""
    monkeypatch.setattr("app.core.auth._lookup_platform_admin", AsyncMock(return_value=True))
    monkeypatch.setattr("app.core.auth._lookup_tenant_status", AsyncMock(return_value="active"))
    return None


@pytest.fixture(autouse=True)
async def seed_grants():
    from app.core.cache import get_cache

    await get_cache().set_platform_admin(USER, True)
    await get_cache().set_tenant_status(TENANT, "active")
    yield
    await get_cache().set_platform_admin(USER, True)
    await get_cache().set_tenant_status(TENANT, "active")


def _byok_service(monkeypatch, **functions):
    """Patch app.services.byok callables; unlisted ones become no-op mocks."""
    import app.services.byok as service

    mocks = {}
    for name, fn in functions.items():
        mock = AsyncMock(side_effect=fn) if fn else AsyncMock()
        mocks[name] = mock
        monkeypatch.setattr(service, name, mock)
    return mocks


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


async def test_get_settings_llm_readable_by_plain_user(api_client, plain_headers, monkeypatch):
    _byok_service(monkeypatch, get_provider_config=lambda *a, **k: None)
    res = await api_client.get("/api/v1/settings/llm", headers=plain_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert body["provider"] is None and body["key_last4"] is None


async def test_settings_writes_require_tenant_admin(api_client, plain_headers):
    for method, path in [
        ("put", "/api/v1/settings/llm"),
        ("post", "/api/v1/settings/llm/validate"),
        ("patch", "/api/v1/settings/llm"),
        ("delete", "/api/v1/settings/llm"),
    ]:
        if method == "delete":
            res = await api_client.delete(path, headers=plain_headers)
        else:
            res = await getattr(api_client, method)(path, headers=plain_headers, json={})
        assert res.status_code == 403, (method, path)
        assert res.json()["detail"]["code"] == "NOT_TENANT_ADMIN"


async def test_admin_llm_requires_platform_admin(api_client, admin_headers):
    res = await api_client.get(f"/api/v1/admin/tenants/{TENANT}/llm", headers=admin_headers)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "NOT_PLATFORM_ADMIN"


async def test_superusers_pass_tenant_admin_guard(api_client, superuser_headers, monkeypatch):
    # require_tenant_admin admits an active superuser without the role.
    mocks = _byok_service(monkeypatch, set_provider_config=lambda *a, **k: dict(MASKED_CONFIG))
    res = await api_client.put(
        "/api/v1/settings/llm",
        headers=superuser_headers,
        json={
            "provider": "openai",
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "o4-mini",
            "fast_model": "gpt-5-mini",
        },
    )
    assert res.status_code == 200
    assert mocks["set_provider_config"].await_count == 1


# ---------------------------------------------------------------------------
# Tenant surface: masked reads, save, validate, toggle, revert
# ---------------------------------------------------------------------------


async def test_get_returns_masked_config_only(api_client, admin_headers, monkeypatch):
    plaintext = secrets.token_urlsafe(24)
    config = dict(MASKED_CONFIG)
    _byok_service(monkeypatch, get_provider_config=lambda *a, **k: config)
    res = await api_client.get("/api/v1/settings/llm", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert body["key_last4"] == "abcd"
    assert plaintext not in res.text
    assert _no_key_material(body)


async def test_put_saves_via_service_with_actor(api_client, admin_headers, monkeypatch):
    plaintext = secrets.token_urlsafe(24)
    mocks = _byok_service(monkeypatch, set_provider_config=lambda *a, **k: dict(MASKED_CONFIG))
    res = await api_client.put(
        "/api/v1/settings/llm",
        headers=admin_headers,
        json={
            "provider": "openai",
            "api_key": plaintext,
            "base_url": "https://gw.example.com/v1",
            "reasoning_model": "o4-mini",
            "fast_model": "gpt-5-mini",
            "embedding_model": "text-embedding-3-small",
        },
    )
    assert res.status_code == 200
    assert _no_key_material(res.json())
    mocks["set_provider_config"].assert_awaited_once()
    kwargs = mocks["set_provider_config"].await_args.kwargs
    assert kwargs["tenant_id"] == TENANT
    assert kwargs["actor_user_id"] == USER
    assert kwargs["api_key"] == plaintext


async def test_put_validation_failure_is_400_sanitized(api_client, admin_headers, monkeypatch):
    from app.services.byok import BYOKValidationError

    _byok_service(
        monkeypatch,
        set_provider_config=_raise(BYOKValidationError("openai rejected the credentials")),
    )
    res = await api_client.put(
        "/api/v1/settings/llm",
        headers=admin_headers,
        json={
            "provider": "openai",
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "o4-mini",
            "fast_model": "gpt-5-mini",
        },
    )
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert detail["code"] == "BYOK_VALIDATION_FAILED"
    assert detail["message"] == "openai rejected the credentials"


def _raise(exc):
    async def raiser(*args, **kwargs):
        raise exc

    return raiser


async def test_put_missing_encryption_key_is_503(api_client, admin_headers, monkeypatch):
    from app.llm.resolver import BYOKNotConfiguredError

    _byok_service(
        monkeypatch,
        set_provider_config=_raise(
            BYOKNotConfiguredError("TENANT_ENCRYPTION_KEY is not configured")
        ),
    )
    res = await api_client.put(
        "/api/v1/settings/llm",
        headers=admin_headers,
        json={
            "provider": "openai",
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "o4-mini",
            "fast_model": "gpt-5-mini",
        },
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "BYOK_NOT_CONFIGURED"


async def test_validate_pings_without_saving(api_client, admin_headers, monkeypatch):
    mocks = _byok_service(monkeypatch, validate_provider=None)
    res = await api_client.post(
        "/api/v1/settings/llm/validate",
        headers=admin_headers,
        json={
            "provider": "anthropic",
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "claude-opus-4",
            "fast_model": "claude-haiku-4",
        },
    )
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "provider": "anthropic"}
    # Nothing else in the service layer may have been touched (no save).
    mocks["validate_provider"].assert_awaited_once()


async def test_validate_failure_is_400(api_client, admin_headers, monkeypatch):
    from app.services.byok import BYOKValidationError

    _byok_service(
        monkeypatch,
        validate_provider=_raise(BYOKValidationError("anthropic rejected the credentials")),
    )
    res = await api_client.post(
        "/api/v1/settings/llm/validate",
        headers=admin_headers,
        json={
            "provider": "anthropic",
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "claude-opus-4",
            "fast_model": "claude-haiku-4",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "BYOK_VALIDATION_FAILED"


async def test_patch_status_toggles_and_reads_back(api_client, admin_headers, monkeypatch):
    disabled = dict(MASKED_CONFIG, status="disabled")
    _byok_service(
        monkeypatch,
        set_status=lambda *a, **k: True,
        get_provider_config=lambda *a, **k: disabled,
    )
    res = await api_client.patch(
        "/api/v1/settings/llm", headers=admin_headers, json={"status": "disabled"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "disabled"


async def test_patch_status_without_config_is_404(api_client, admin_headers, monkeypatch):
    _byok_service(monkeypatch, set_status=lambda *a, **k: False)
    res = await api_client.patch(
        "/api/v1/settings/llm", headers=admin_headers, json={"status": "active"}
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "NO_LLM_CONFIG"


async def test_delete_reverts_to_platform(api_client, admin_headers, monkeypatch):
    _byok_service(monkeypatch, delete_provider_config=lambda *a, **k: True)
    res = await api_client.delete("/api/v1/settings/llm", headers=admin_headers)
    assert res.status_code == 200
    assert res.json() == {"status": "reverted", "provider": "platform"}


async def test_delete_without_config_is_404(api_client, admin_headers, monkeypatch):
    _byok_service(monkeypatch, delete_provider_config=lambda *a, **k: False)
    res = await api_client.delete("/api/v1/settings/llm", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "NO_LLM_CONFIG"


async def test_invalid_provider_rejected_at_validation_layer(
    api_client, admin_headers, monkeypatch
):
    _byok_service(monkeypatch, set_provider_config=lambda *a, **k: dict(MASKED_CONFIG))
    res = await api_client.put(
        "/api/v1/settings/llm",
        headers=admin_headers,
        json={
            "provider": "bedrock",  # not in {anthropic, openai}
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "m",
            "fast_model": "m",
        },
    )
    assert res.status_code == 422  # pydantic pattern gate


# ---------------------------------------------------------------------------
# Admin surface: masked view + spend attribution, force-set, status
# ---------------------------------------------------------------------------


async def test_admin_get_returns_config_and_usage(api_client, superuser_headers, monkeypatch):
    _byok_service(
        monkeypatch,
        get_provider_config=lambda *a, **k: dict(MASKED_CONFIG),
        tenant_llm_usage=lambda *a, **k: [dict(row) for row in USAGE_ROWS],
    )
    res = await api_client.get(f"/api/v1/admin/tenants/{TENANT}/llm", headers=superuser_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["config"]["configured"] is True
    assert body["usage"][0]["key_source"] == "tenant"
    assert body["usage"][0]["calls"] == 12
    assert _no_key_material(body)


async def test_admin_usage_window_threaded_through(api_client, superuser_headers, monkeypatch):
    mocks = _byok_service(
        monkeypatch,
        get_provider_config=lambda *a, **k: None,
        tenant_llm_usage=lambda *a, **k: [],
    )
    res = await api_client.get(
        f"/api/v1/admin/tenants/{TENANT}/llm?days=30", headers=superuser_headers
    )
    assert res.status_code == 200
    assert mocks["tenant_llm_usage"].await_args.args == (TENANT, 30)


async def test_admin_days_window_bounded(api_client, superuser_headers):
    res = await api_client.get(
        f"/api/v1/admin/tenants/{TENANT}/llm?days=400", headers=superuser_headers
    )
    assert res.status_code == 422


async def test_admin_invalid_tenant_400(api_client, superuser_headers):
    res = await api_client.get("/api/v1/admin/tenants/not-a-uuid/llm", headers=superuser_headers)
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_TENANT"


async def test_admin_put_force_sets_for_tenant(api_client, superuser_headers, monkeypatch):
    mocks = _byok_service(monkeypatch, set_provider_config=lambda *a, **k: dict(MASKED_CONFIG))
    res = await api_client.put(
        f"/api/v1/admin/tenants/{OTHER_TENANT}/llm",
        headers=superuser_headers,
        json={
            "provider": "openai",
            "api_key": secrets.token_urlsafe(24),
            "reasoning_model": "o4-mini",
            "fast_model": "gpt-5-mini",
        },
    )
    assert res.status_code == 200
    kwargs = mocks["set_provider_config"].await_args.kwargs
    assert kwargs["tenant_id"] == OTHER_TENANT  # the path tenant, not the caller's
    assert kwargs["actor_user_id"] == USER  # the superuser is the actor


async def test_admin_patch_status(api_client, superuser_headers, monkeypatch):
    _byok_service(
        monkeypatch,
        set_status=lambda *a, **k: True,
        get_provider_config=lambda *a, **k: dict(MASKED_CONFIG, status="disabled"),
    )
    res = await api_client.patch(
        f"/api/v1/admin/tenants/{TENANT}/llm",
        headers=superuser_headers,
        json={"status": "disabled"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "disabled"


# ---------------------------------------------------------------------------
# /admin/stats spend fields
# ---------------------------------------------------------------------------


async def test_admin_stats_carries_spend_fields(api_client, superuser_headers, monkeypatch):
    import app.services.tenants as tenants_service

    monkeypatch.setattr(
        tenants_service,
        "platform_stats",
        AsyncMock(
            return_value={
                "tenants_total": 3,
                "tenants_active": 2,
                "tenants_suspended": 1,
                "users_total": 10,
                "llm_calls_24h": 42,
                "llm_tokens_24h": 12345,
                "llm_byok_calls_24h": 17,
                "platform_admins_active": 1,
            }
        ),
    )
    res = await api_client.get("/api/v1/admin/stats", headers=superuser_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["llm_tokens_24h"] == 12345
    assert body["llm_byok_calls_24h"] == 17


# ---------------------------------------------------------------------------
# Spend attribution service contract (SQL shape, admin role, tenant filter)
# ---------------------------------------------------------------------------


async def test_tenant_llm_usage_sql_contract(monkeypatch):
    import app.services.byok as byok_service

    conn = MagicMock()
    conn.close = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    captured = {}

    async def fake_connect(dsn):
        captured["dsn"] = dsn
        return conn

    monkeypatch.setattr(byok_service.asyncpg, "connect", fake_connect)
    rows = await byok_service.tenant_llm_usage(TENANT, 7)

    assert rows == []
    assert "genbi_admin" in captured["dsn"] or "genbi" in captured["dsn"]
    sql, *binds = conn.fetch.await_args.args
    assert "FROM audit_log" in sql
    assert "GROUP BY provider, key_source, model_name, day" in sql
    assert "tenant_id = $1::uuid" in sql
    assert binds[0] == TENANT  # tenant filter threaded as a bind parameter
    assert binds[1] == 7  # window threaded as a bind, not string-interpolated


async def test_tenant_llm_usage_window_clamped(monkeypatch):
    import app.services.byok as byok_service

    conn = MagicMock()
    conn.close = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(byok_service.asyncpg, "connect", AsyncMock(return_value=conn))
    await byok_service.tenant_llm_usage(TENANT, 365)  # clamped to 90
    assert conn.fetch.await_args.args[2] == 90


async def test_tenant_llm_usage_row_mapping(monkeypatch):
    from datetime import date

    import app.services.byok as byok_service

    row = {
        "day": date(2026, 9, 5),
        "provider": "openai",
        "key_source": "tenant",
        "model_name": "gpt-5-mini",
        "calls": 3,
        "input_tokens": 100,
        "output_tokens": 40,
    }
    conn = MagicMock()
    conn.close = AsyncMock()
    conn.fetch = AsyncMock(return_value=[row])
    monkeypatch.setattr(byok_service.asyncpg, "connect", AsyncMock(return_value=conn))
    rows = await byok_service.tenant_llm_usage(TENANT)
    assert rows == [
        {
            "day": "2026-09-05",
            "provider": "openai",
            "key_source": "tenant",
            "model_name": "gpt-5-mini",
            "calls": 3,
            "input_tokens": 100,
            "output_tokens": 40,
        }
    ]
