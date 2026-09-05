"""Phase 25 BYOK tests: adapters, resolver, no-fallback policy, audit
attribution, embeddings routing — all external I/O faked (offline).

Test-only key material is generated at runtime — no credential literals in
source (they are throwaways against fakes, never real secrets).
"""

import asyncio
import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.llm.providers.base import AdapterCall, ProviderAuthError
from app.llm.resolver import (
    BYOKNotConfiguredError,
    ResolvedLLM,
    _resolution_cache,
    invalidate_resolution,
    resolve_llm,
)

TENANT = "00000000-0000-0000-0000-000000000001"

PLATFORM_KEY = secrets.token_urlsafe(16)
TENANT_KEY = secrets.token_urlsafe(16)

PLATFORM = ResolvedLLM(
    provider="anthropic",
    base_url=None,
    api_key=PLATFORM_KEY,
    reasoning_model="claude-opus-4",
    fast_model="claude-haiku-4",
    embedding_model=None,
    source="platform",
    key_version=None,
    tenant_id=None,
)

TENANT_CFG = ResolvedLLM(
    provider="openai",
    base_url="https://gw.example.com/v1",
    api_key=TENANT_KEY,
    reasoning_model="o4-mini",
    fast_model="gpt-5-mini",
    embedding_model="text-embedding-3-small",
    source="tenant",
    key_version=3,
    tenant_id=TENANT,
)


def _call(model="m", response_format=None, thinking=False):
    return AdapterCall(
        messages="hello",
        system="be brief",
        model=model,
        temperature=0.0,
        max_tokens=100,
        thinking=thinking,
        response_format=response_format,
        timeout=15,
    )


@pytest.fixture(autouse=True)
def clean_resolution_cache():
    _resolution_cache.clear()
    yield
    _resolution_cache.clear()


# ---------------------------------------------------------------------------
# Adapters (parity matrix, mocked SDKs)
# ---------------------------------------------------------------------------


def test_anthropic_adapter_passes_model_and_system():
    from app.llm.providers.anthropic_provider import AnthropicAdapter

    captured = {}

    class FakeResponse:
        content = "hi"
        usage_metadata = {"input_tokens": 4, "output_tokens": 2}

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def invoke(self, messages, system=""):
            captured["messages"] = messages
            captured["system"] = system
            return FakeResponse()

    key = secrets.token_urlsafe(12)
    with patch("langchain_anthropic.ChatAnthropic", FakeChatAnthropic):
        result = AnthropicAdapter(api_key=key).invoke(_call(thinking=True))

    assert result.content == "hi"
    assert result.input_tokens == 4 and result.output_tokens == 2
    assert captured["api_key"] == key
    assert captured["model"] == "m"
    assert captured["system"] == "be brief"
    assert captured["model_kwargs"]["thinking"]["type"] == "enabled"


def test_anthropic_adapter_auth_error_mapping():
    from app.llm.providers.anthropic_provider import AnthropicAdapter

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages, system=""):
            raise RuntimeError("Error code: 401 - authentication_error invalid x-api-key")

    with patch("langchain_anthropic.ChatAnthropic", FakeChatAnthropic):
        with pytest.raises(ProviderAuthError):
            AnthropicAdapter(api_key=secrets.token_urlsafe(8)).invoke(_call())


def test_openai_adapter_contract():
    from app.llm.providers.openai_provider import OpenAIAdapter

    captured = {}

    class FakeUsage:
        prompt_tokens = 7
        completion_tokens = 3

    class FakeResponse:
        usage = FakeUsage()

        def __init__(self):
            self.choices = [MagicMock(message=MagicMock(content="yo"))]

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            self.chat = MagicMock(completions=FakeCompletions())

    key = secrets.token_urlsafe(12)
    with patch("openai.OpenAI", FakeClient):
        result = OpenAIAdapter(api_key=key, base_url="https://gw/v1").invoke(
            _call(response_format="json")
        )

    assert result.content == "yo"
    assert result.input_tokens == 7 and result.output_tokens == 3
    assert captured["api_key"] == key and captured["base_url"] == "https://gw/v1"
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"][0]["role"] == "system"  # system prompt first
    assert "thinking" not in captured  # documented no-op


def test_openai_adapter_auth_error_mapping():
    from app.llm.providers.openai_provider import OpenAIAdapter

    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("401 invalid_api_key: Incorrect API key provided")

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = MagicMock(completions=FakeCompletions())

    with patch("openai.OpenAI", FakeClient), pytest.raises(ProviderAuthError):
        OpenAIAdapter(api_key=secrets.token_urlsafe(8)).invoke(_call())


def test_openai_chat_langchain_wrapper():
    from app.llm.providers.openai_provider import OpenAIChat

    adapter = MagicMock()
    adapter.invoke = lambda call: MagicMock(content="wrapped", input_tokens=1, output_tokens=2)
    chat = OpenAIChat(
        api_key="k",
        base_url=None,
        model="m",
        temperature=0.0,
        max_tokens=10,
        timeout=5,
        response_format=None,
    )
    chat._adapter = adapter

    result = asyncio.run(chat.ainvoke([MagicMock(content="q")], system="s"))
    assert result.content == "wrapped"
    assert result.usage_metadata == {"input_tokens": 1, "output_tokens": 2}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def _fake_cache(monkeypatch, version=None):
    cache = MagicMock()
    cache.get_byok_version = AsyncMock(return_value=version)
    cache.set_byok_version = AsyncMock()
    monkeypatch.setattr("app.core.cache.get_cache", lambda: cache)
    return cache


async def test_resolve_no_tenant_returns_platform():
    resolved = await resolve_llm(None)
    assert resolved.source == "platform" and resolved.provider == "anthropic"


async def test_resolve_no_row_falls_to_platform(monkeypatch):
    _fake_cache(monkeypatch)

    async def fake_load(tenant_id):
        return None

    monkeypatch.setattr("app.llm.resolver._load", fake_load)
    resolved = await resolve_llm(TENANT)
    assert resolved.source == "platform"


async def test_resolve_tenant_row_used_and_cached(monkeypatch):
    cache = _fake_cache(monkeypatch)

    async def fake_load(tenant_id):
        return TENANT_CFG

    load = AsyncMock(side_effect=fake_load)
    monkeypatch.setattr("app.llm.resolver._load", load)

    first = await resolve_llm(TENANT)
    assert first.source == "tenant" and first.api_key == TENANT_KEY
    cache.set_byok_version.assert_awaited_once_with(TENANT, 3)

    # Second call with the cached version hits the in-memory resolution.
    cache.get_byok_version = AsyncMock(return_value=3)
    second = await resolve_llm(TENANT)
    assert second is first
    load.assert_awaited_once()


async def test_rotation_invalidates_cache(monkeypatch):
    cache = _fake_cache(monkeypatch)
    cache.get_byok_version = AsyncMock(return_value=3)
    _resolution_cache[(TENANT, 3)] = TENANT_CFG

    invalidate_resolution(TENANT)
    assert (TENANT, 3) not in _resolution_cache

    rotated = ResolvedLLM(**{**TENANT_CFG.__dict__, "key_version": 4})

    async def fake_load(tenant_id):
        return rotated

    monkeypatch.setattr("app.llm.resolver._load", fake_load)
    cache.get_byok_version = AsyncMock(return_value=None)
    resolved = await resolve_llm(TENANT)
    assert resolved.key_version == 4
    assert (TENANT, 4) in _resolution_cache


async def test_missing_encryption_key_raises_not_fallback(monkeypatch):
    """A configured tenant + unset platform key must NOT fall to platform."""
    _fake_cache(monkeypatch)

    async def fake_load(tenant_id):
        raise BYOKNotConfiguredError("TENANT_ENCRYPTION_KEY is not configured")

    monkeypatch.setattr("app.llm.resolver._load", fake_load)
    with pytest.raises(BYOKNotConfiguredError):
        await resolve_llm(TENANT)


async def test_control_plane_outage_fails_open_to_platform(monkeypatch):
    _fake_cache(monkeypatch)

    async def fake_load(tenant_id):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.llm.resolver._load", fake_load)
    resolved = await resolve_llm(TENANT)
    assert resolved.source == "platform"


# ---------------------------------------------------------------------------
# LLMClient no-fallback policy + audit attribution
# ---------------------------------------------------------------------------


def _patch_resolve(monkeypatch, resolved):
    async def fake_resolve(tenant_id):
        return resolved

    # The client binds resolve_llm lazily inside invoke — patch the module.
    import app.llm.resolver as resolver_module

    monkeypatch.setattr(resolver_module, "resolve_llm", fake_resolve)


def _evil_llm(monkeypatch, client, exc):
    evil = MagicMock()

    async def evil_ainvoke(*a, **k):
        raise exc

    evil.ainvoke = evil_ainvoke
    monkeypatch.setattr(type(client), "_build_llm", lambda self, *a, **k: evil, raising=False)


class _OneRetryOptions:
    max_retries = 1
    token_budget = 100_000
    thinking = False


async def test_no_fallback_on_tenant_auth_error(monkeypatch):
    from app.core.llm_client import LLMBYOKMisconfiguredError, get_llm_client

    _patch_resolve(monkeypatch, TENANT_CFG)
    client = get_llm_client()
    _evil_llm(monkeypatch, client, ProviderAuthError("rejected"))

    with pytest.raises(LLMBYOKMisconfiguredError):
        await client.invoke(messages="q", tenant_id=TENANT, options=None)


async def test_platform_auth_error_raises_raw(monkeypatch):
    """Platform-source auth errors are NOT BYOK misconfigurations."""
    from app.core.llm_client import get_llm_client

    _patch_resolve(monkeypatch, PLATFORM)
    client = get_llm_client()
    _evil_llm(monkeypatch, client, ProviderAuthError("platform key issue"))

    with pytest.raises(ProviderAuthError):
        await client.invoke(messages="q", tenant_id=TENANT, options=_OneRetryOptions())


async def test_audit_receives_byok_attribution(monkeypatch):
    from app.core.llm_client import get_llm_client

    _patch_resolve(monkeypatch, TENANT_CFG)
    client = get_llm_client()

    good = MagicMock()

    async def good_ainvoke(messages, system=""):
        return MagicMock(content="ok", usage_metadata={"input_tokens": 1, "output_tokens": 1})

    good.ainvoke = good_ainvoke
    monkeypatch.setattr(type(client), "_build_llm", lambda self, *a, **k: good, raising=False)

    captured_audit = {}

    async def fake_audit(**kwargs):
        captured_audit.update(kwargs)

    monkeypatch.setattr(client, "_audit", fake_audit)

    result = await client.invoke(messages="q", tenant_id=TENANT)
    assert result.content == "ok"
    assert captured_audit["provider"] == "openai"
    assert captured_audit["key_source"] == "tenant"
    assert captured_audit["key_version"] == 3


# ---------------------------------------------------------------------------
# Embeddings routing (ADR 011 §9)
# ---------------------------------------------------------------------------


_patchers = []


@pytest.fixture(autouse=True)
def _stop_openai_patches():
    yield
    while _patchers:
        _patchers.pop()()


def _fake_openai_module(monkeypatch, captured):
    class FakeCreate:
        async def create(self, **kwargs):
            captured.update(kwargs)
            m = MagicMock()
            m.data = [MagicMock(embedding=[0.1] * settings.EMBEDDING_DIMS)]
            return m

    fake_client = MagicMock()
    fake_client.embeddings = FakeCreate()
    factory = MagicMock(return_value=fake_client)
    patcher = patch("openai.AsyncOpenAI", factory)
    patcher.start()
    _patchers.append(patcher.stop)
    return factory


async def test_embeddings_platform_without_tenant(monkeypatch):
    import app.core.embeddings as emb

    captured = {}
    factory = _fake_openai_module(monkeypatch, captured)

    fake_platform_key = secrets.token_urlsafe(12)
    with patch.object(emb.settings, "OPENAI_API_KEY", fake_platform_key):
        await emb.embed_text("hello")
    assert captured["model"] == settings.EMBEDDING_MODEL
    assert factory.call_args.kwargs["api_key"] == fake_platform_key


async def test_embeddings_ride_tenant_key(monkeypatch):
    import app.core.embeddings as emb

    async def fake_resolve(tenant_id):
        return TENANT_CFG  # provider=openai + embedding_model

    monkeypatch.setattr("app.llm.resolver.resolve_llm", fake_resolve)

    captured = {}
    factory = _fake_openai_module(monkeypatch, captured)

    await emb.embed_text("hello", tenant_id=TENANT)

    assert captured["model"] == "text-embedding-3-small"  # tenant model
    assert factory.call_args.kwargs["api_key"] == TENANT_KEY


async def test_embeddings_anthropic_tenant_stays_platform(monkeypatch):
    """Anthropic tenants have no embeddings API — the platform key is used."""
    import app.core.embeddings as emb

    anthropic_cfg = ResolvedLLM(**{**TENANT_CFG.__dict__, "provider": "anthropic"})

    async def fake_resolve(tenant_id):
        return anthropic_cfg

    monkeypatch.setattr("app.llm.resolver.resolve_llm", fake_resolve)

    captured = {}
    factory = _fake_openai_module(monkeypatch, captured)

    with patch.object(emb.settings, "OPENAI_API_KEY", ""), pytest.raises(RuntimeError):
        await emb.embed_text("hello", tenant_id=TENANT)


# ---------------------------------------------------------------------------
# Storage service (masked reads, crypto-in-SQL, version bump)
# ---------------------------------------------------------------------------


async def test_set_provider_config_contract(monkeypatch):
    import app.services.byok as byok

    conn = MagicMock()
    conn.close = AsyncMock()
    conn.execute = AsyncMock(return_value="SET")
    row = {
        "provider": "openai",
        "base_url": None,
        "reasoning_model": "o4-mini",
        "fast_model": "gpt-5-mini",
        "embedding_model": None,
        "key_last4": TENANT_KEY[-4:],
        "key_version": 2,
        "status": "active",
        "updated_at": __import__("datetime").datetime(
            2026, 9, 5, tzinfo=__import__("datetime").UTC
        ),
    }
    conn.fetchrow = AsyncMock(return_value=row)

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(byok.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(byok, "validate_provider", AsyncMock())
    import app.services.admin_audit as _aa

    monkeypatch.setattr(_aa, "record_admin_action", AsyncMock(return_value=True))
    monkeypatch.setattr(byok.settings, "TENANT_ENCRYPTION_KEY", secrets.token_urlsafe(24))

    result = await byok.set_provider_config(TENANT, "openai", TENANT_KEY, "o4-mini", "gpt-5-mini")
    assert result["key_last4"] == TENANT_KEY[-4:] and result["key_version"] == 2
    assert "api_key" not in result and "api_key_enc" not in result  # masked

    call = conn.fetchrow.call_args
    sql = call.args[0]
    # Encryption happens inside SQL; the plaintext never enters the SQL text
    assert "app_crypto.encrypt($7, $8)" in sql
    assert TENANT_KEY not in sql
    # ...but rides as a bound parameter
    assert call.args[8] == TENANT_KEY


async def test_set_provider_requires_encryption_key(monkeypatch):
    import app.services.byok as byok

    monkeypatch.setattr(byok.settings, "TENANT_ENCRYPTION_KEY", "")
    monkeypatch.setattr(byok, "validate_provider", AsyncMock())
    with pytest.raises(BYOKNotConfiguredError):
        await byok.set_provider_config(TENANT, "openai", TENANT_KEY, "m1", "m2")


async def test_validation_failure_sanitized(monkeypatch):
    # Fail at the SDK layer (inside the REAL validate_provider wrapper) so
    # the sanitization contract is what's under test.
    import app.llm.providers.base as base_module
    import app.services.byok as byok

    def boom(provider, api_key, call, base_url=None):
        raise RuntimeError("raw provider 401 details")

    monkeypatch.setattr(base_module, "invoke", boom)
    monkeypatch.setattr(byok.settings, "TENANT_ENCRYPTION_KEY", secrets.token_urlsafe(24))
    with pytest.raises(byok.BYOKValidationError) as exc_info:
        await byok.set_provider_config(TENANT, "openai", TENANT_KEY, "m1", "m2")
    assert "raw provider" not in str(exc_info.value)  # message sanitized


# ---------------------------------------------------------------------------
# Supplementary matrix (task 132): dispatch, disabled-status routing,
# cache contracts, status/delete storage paths, audit key-absence
# ---------------------------------------------------------------------------


def test_base_invoke_dispatches_by_provider():
    """The module-level dispatch picks the right adapter per provider."""
    from app.llm.providers import base as base_module

    calls = []

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            calls.append(("openai", api_key, base_url))

        def invoke(self, call):
            return MagicMock(content="via-openai")

    class FakeAnthropic:
        def __init__(self, api_key, base_url):
            calls.append(("anthropic", api_key, base_url))

        def invoke(self, call):
            return MagicMock(content="via-anthropic")

    key = secrets.token_urlsafe(8)
    with patch("app.llm.providers.openai_provider.OpenAIAdapter", FakeOpenAI):
        result = base_module.invoke("openai", key, _call(), base_url="https://gw/v1")
    assert result.content == "via-openai"
    assert calls[-1] == ("openai", key, "https://gw/v1")

    with patch("app.llm.providers.anthropic_provider.AnthropicAdapter", FakeAnthropic):
        result = base_module.invoke("anthropic", key, _call())
    assert result.content == "via-anthropic"
    assert calls[-1] == ("anthropic", key, None)


async def test_resolve_disabled_row_falls_to_platform(monkeypatch):
    """status=disabled is the explicit revert switch (offline proof).

    The resolver's query filters status='active', so a disabled row never
    reaches resolution — modeled here by _load returning None."""
    import app.llm.resolver as resolver_module

    _fake_cache(monkeypatch)

    async def fake_load(tenant_id):
        return None

    monkeypatch.setattr(resolver_module, "_load", fake_load)
    resolved = await resolve_llm(TENANT)
    assert resolved.source == "platform"


async def test_platform_resolution_is_cached_for_tenant(monkeypatch):
    """A platform resolution for a tenant caches under version 0 and is
    reused (no repeated loads)."""
    import app.llm.resolver as resolver_module

    cache = _fake_cache(monkeypatch)

    async def fake_load(tenant_id):
        return None

    load = AsyncMock(side_effect=fake_load)
    monkeypatch.setattr(resolver_module, "_load", load)

    first = await resolve_llm(TENANT)
    assert first.source == "platform"
    cache.set_byok_version.assert_awaited_once_with(TENANT, 0)

    cache.get_byok_version = AsyncMock(return_value=0)
    second = await resolve_llm(TENANT)
    assert second.source == "platform"
    load.assert_awaited_once()  # second call was cache-served


async def test_cache_byok_version_roundtrip():
    from app.core.cache import CacheService

    cache = CacheService()
    await cache.set_byok_version(TENANT, 7)
    assert await cache.get_byok_version(TENANT) == 7


def test_require_encryption_key_rejects_placeholders(monkeypatch):
    from app.llm.resolver import _require_encryption_key

    monkeypatch.setattr(settings, "TENANT_ENCRYPTION_KEY", "")
    with pytest.raises(BYOKNotConfiguredError):
        _require_encryption_key()

    monkeypatch.setattr(settings, "TENANT_ENCRYPTION_KEY", "change-me-in-production")
    with pytest.raises(BYOKNotConfiguredError):
        _require_encryption_key()

    real = secrets.token_urlsafe(24)
    monkeypatch.setattr(settings, "TENANT_ENCRYPTION_KEY", real)
    assert _require_encryption_key() == real


def test_platform_default_shape():
    from app.llm.resolver import platform_default

    resolved = platform_default()
    assert resolved.provider == "anthropic"
    assert resolved.source == "platform"
    assert resolved.key_version is None
    assert resolved.reasoning_model == settings.LLM_REASONING_MODEL
    assert resolved.fast_model == settings.LLM_FAST_MODEL


async def test_set_status_and_delete_contracts(monkeypatch):
    import app.services.byok as byok

    conn = MagicMock()
    conn.close = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchrow = AsyncMock(return_value=None)

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(byok.asyncpg, "connect", fake_connect)

    assert await byok.set_status(TENANT, "disabled") is True
    status_call = conn.execute.call_args_list[-1]
    assert "UPDATE tenant_llm_providers SET status" in status_call.args[0]
    assert status_call.args[1:] == (TENANT, "disabled", None)

    conn.execute = AsyncMock(return_value="DELETE 1")
    assert await byok.delete_provider_config(TENANT) is True
    delete_call = conn.execute.call_args_list[-1]
    assert "DELETE FROM tenant_llm_providers WHERE tenant_id = $1::uuid" in delete_call.args[0]

    conn.execute = AsyncMock(return_value="UPDATE 0")
    assert await byok.set_status(TENANT, "active") is False


async def test_get_provider_config_masked_only(monkeypatch):
    import app.services.byok as byok

    conn = MagicMock()
    conn.close = AsyncMock()
    conn.execute = AsyncMock(return_value="SET")
    row = {
        "provider": "anthropic",
        "base_url": None,
        "reasoning_model": "claude-opus-4",
        "fast_model": "claude-haiku-4",
        "embedding_model": None,
        "key_last4": "wxyz",
        "key_version": 1,
        "status": "active",
        "updated_at": __import__("datetime").datetime(
            2026, 9, 5, tzinfo=__import__("datetime").UTC
        ),
    }
    conn.fetchrow = AsyncMock(return_value=row)

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(byok.asyncpg, "connect", fake_connect)
    masked = await byok.get_provider_config(TENANT)
    assert set(masked) == {
        "provider",
        "base_url",
        "reasoning_model",
        "fast_model",
        "embedding_model",
        "key_last4",
        "key_version",
        "status",
        "updated_at",
    }  # no api_key / api_key_enc anywhere

    sql = conn.fetchrow.call_args.args[0]
    assert "api_key_enc" not in sql  # the read never even selects the ciphertext


async def test_audit_payload_never_contains_key_material(monkeypatch):
    from app.core.llm_client import get_llm_client

    _patch_resolve(monkeypatch, TENANT_CFG)
    client = get_llm_client()

    good = MagicMock()

    async def good_ainvoke(messages, system=""):
        return MagicMock(content="ok", usage_metadata={"input_tokens": 1, "output_tokens": 1})

    good.ainvoke = good_ainvoke
    monkeypatch.setattr(type(client), "_build_llm", lambda self, *a, **k: good, raising=False)

    captured = {}

    async def fake_audit(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(client, "_audit", fake_audit)
    await client.invoke(messages="q", tenant_id=TENANT)

    serialized = repr(captured)
    assert TENANT_KEY not in serialized  # key material never reaches audit


async def test_validate_provider_builds_ping_call(monkeypatch):
    import app.services.byok as byok

    captured = {}

    def fake_invoke(provider, api_key, call, base_url=None):
        captured.update(
            provider=provider,
            api_key=api_key,
            model=call.model,
            max_tokens=call.max_tokens,
            messages=call.messages,
            base_url=base_url,
        )
        return MagicMock(content="ok")

    import app.llm.providers.base as base_module

    monkeypatch.setattr(base_module, "invoke", fake_invoke)
    key = secrets.token_urlsafe(10)
    await byok.validate_provider("openai", key, "https://gw/v1", "gpt-5-mini")

    assert captured["provider"] == "openai"
    assert captured["api_key"] == key
    assert captured["model"] == "gpt-5-mini"
    assert captured["max_tokens"] == 1  # the 1-token ping
    assert captured["messages"] == "ping"
    assert captured["base_url"] == "https://gw/v1"
