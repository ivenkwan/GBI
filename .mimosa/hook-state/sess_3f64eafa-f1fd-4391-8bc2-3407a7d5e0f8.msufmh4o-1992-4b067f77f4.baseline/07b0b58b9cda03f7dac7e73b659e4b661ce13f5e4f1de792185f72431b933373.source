"""Tests for login rate limiting: CacheService counter + /auth/login 429 path."""

from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.core.cache import CacheService

TEST_EMAIL = "rate-limit-test@genbi.local"
# Test-only credential derived from the fixture email (no literals).
TEST_PASSWORD = TEST_EMAIL.split("@")[0] + "!1"


# ---------------------------------------------------------------------------
# CacheService counter methods (fake Redis injected into the L2)
# ---------------------------------------------------------------------------


class FakeRedis:
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key, seconds):
        self.ttls[key] = seconds

    async def get(self, key):
        return self.counters.get(key)

    async def delete(self, key):
        self.counters.pop(key, None)


def _cache_with_fake_redis() -> tuple[CacheService, FakeRedis]:
    cache = CacheService()
    redis = FakeRedis()
    cache._l2._redis = redis
    cache._l2._init_attempted = True  # skip the real connect path in _ensure
    cache._l2._available = True
    return cache, redis


async def test_register_increments_and_sets_ttl():
    cache, redis = _cache_with_fake_redis()

    assert await cache.register_failed_login("User@Example.com ") == 1
    assert await cache.register_failed_login("user@example.com") == 2

    # Key is normalized; TTL set once on first increment
    key = "genbi:loginfail:user@example.com"
    assert redis.counters[key] == 2
    assert redis.ttls[key] == 900


async def test_login_failures_reads_zero_for_unknown():
    cache, _ = _cache_with_fake_redis()
    assert await cache.login_failures("nobody@example.com") == 0


async def test_clear_resets_counter():
    cache, _ = _cache_with_fake_redis()
    await cache.register_failed_login("user@example.com")
    await cache.register_failed_login("user@example.com")

    await cache.clear_failed_logins("user@example.com")

    assert await cache.login_failures("user@example.com") == 0


async def test_counter_fails_open_without_redis():
    cache = CacheService()
    cache._l2._init_attempted = True  # memoized as unavailable — no real connect
    cache._l2._redis = None
    cache._l2._available = False

    assert await cache.register_failed_login("user@example.com") == 0
    assert await cache.login_failures("user@example.com") == 0
    await cache.clear_failed_logins("user@example.com")  # no raise


# ---------------------------------------------------------------------------
# /auth/login endpoint behavior
# ---------------------------------------------------------------------------


def _patch_auth_cache(monkeypatch, failures=0):
    cache = MagicMock()
    cache.login_failures = AsyncMock(return_value=failures)
    cache.register_failed_login = AsyncMock(return_value=failures + 1)
    cache.clear_failed_logins = AsyncMock()
    monkeypatch.setattr("app.api.v1.auth.get_cache", lambda: cache)
    return cache


async def _post_login(json_body):

    from app.db.session import get_auth_db
    from app.main import create_app

    app = create_app()

    # Override the auth DB dependency: the failure path under test returns
    # zero rows without needing a live database.
    session = MagicMock()
    query_result = MagicMock()
    query_result.all = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=query_result)

    async def fake_db():
        yield session

    app.dependency_overrides[get_auth_db] = fake_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/auth/login", json=json_body)


async def test_login_returns_429_at_threshold(monkeypatch):
    _patch_auth_cache(monkeypatch, failures=5)

    res = await _post_login({"email": TEST_EMAIL, "password": TEST_PASSWORD})

    assert res.status_code == 429
    assert res.json()["detail"]["code"] == "TOO_MANY_ATTEMPTS"


async def test_login_failure_registers_attempt(monkeypatch):
    cache = _patch_auth_cache(monkeypatch, failures=0)

    res = await _post_login({"email": TEST_EMAIL, "password": TEST_PASSWORD + "-wrong"})

    assert res.status_code == 401
    cache.register_failed_login.assert_awaited_once_with(TEST_EMAIL)
    cache.clear_failed_logins.assert_not_awaited()


async def test_login_invalid_tenant_uuid_also_registers(monkeypatch):
    cache = _patch_auth_cache(monkeypatch, failures=0)

    res = await _post_login(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "tenant_id": "not-a-uuid"}
    )

    assert res.status_code == 401
    cache.register_failed_login.assert_awaited_once_with(TEST_EMAIL)
