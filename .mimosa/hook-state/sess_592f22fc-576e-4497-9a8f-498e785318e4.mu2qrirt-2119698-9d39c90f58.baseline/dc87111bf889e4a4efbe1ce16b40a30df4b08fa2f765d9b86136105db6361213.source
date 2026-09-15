"""Tests for Phase 10 CubeClient: tenant-scoped auth tokens and query()."""

from jose import jwt as jose_jwt

from app.semantic.cube_client import CubeClient

SECRET = "test-secret"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"


def _client() -> CubeClient:
    return CubeClient(api_url="http://fake-cube:4000/cubejs-api/v1", api_secret=SECRET)


# ---------------------------------------------------------------------------
# Tenant-scoped tokens
# ---------------------------------------------------------------------------


def test_anonymous_token_has_no_tenant_claim():
    token = _client()._auth_token()
    payload = jose_jwt.decode(token, SECRET, algorithms=["HS256"])
    assert "tenantId" not in payload


def test_tenant_token_carries_claim():
    token = _client()._auth_token(tenant_id=TENANT_A)
    payload = jose_jwt.decode(token, SECRET, algorithms=["HS256"])
    assert payload["tenantId"] == TENANT_A


def test_tokens_cached_per_tenant():
    client = _client()

    a1 = client._auth_token(tenant_id=TENANT_A)
    a2 = client._auth_token(tenant_id=TENANT_A)
    b = client._auth_token(tenant_id=TENANT_B)
    anon = client._auth_token()

    assert a1 == a2, "same tenant should reuse its cached token"
    assert a1 != b, "different tenants must get different tokens"
    assert a1 != anon


# ---------------------------------------------------------------------------
# query()
# ---------------------------------------------------------------------------


class FakeTransport:
    """Captures the last request and replays a canned /load response."""

    def __init__(self, response: dict):
        self.response = response
        self.last_json_body: dict | None = None
        self.last_headers: dict = {}

    async def __call__(self, path, method="GET", json_body=None, tenant_id=None):
        self.last_json_body = json_body
        self.tenant_id = tenant_id
        return self.response


LOAD_RESPONSE = {
    "query": {"measures": ["Sales.revenue_total"]},
    "data": [
        {"Sales.revenue_total": 120000, "Sales.region": "North"},
        {"Sales.revenue_total": 95000, "Sales.region": "South"},
    ],
    "annotation": {
        "measures": {"Sales.revenue_total": {"title": "Total Revenue", "type": "sum"}},
        "dimensions": {"Sales.region": {"title": "Region", "type": "string"}},
    },
}


async def test_query_flattens_and_totals(monkeypatch):
    client = _client()
    transport = FakeTransport(LOAD_RESPONSE)
    monkeypatch.setattr(client, "_request", transport)

    result = await client.query(
        metrics=["Sales.revenue_total"],
        dimensions=["Sales.region"],
        tenant_id=TENANT_A,
    )

    # Flattened rows strip the cube prefix
    assert result.data[0] == {"revenue_total": 120000, "region": "North"}
    # Single-metric total sums the qualified keys
    assert result.total == 215000
    assert result.metric_name == "Sales.revenue_total"
    assert result.annotation["measures"]["Sales.revenue_total"]["type"] == "sum"
    assert result.query_latency_ms >= 0


async def test_query_payload_shape(monkeypatch):
    client = _client()
    transport = FakeTransport({"data": [], "annotation": {}})
    monkeypatch.setattr(client, "_request", transport)

    await client.query(
        metrics=["Sales.revenue_total"],
        dimensions=["Sales.region"],
        time_dimensions=[{"dimension": "Sales.transaction_date", "granularity": "month"}],
        order=[["Sales.revenue_total", "desc"]],
        limit=50,
        tenant_id=TENANT_A,
    )

    assert transport.tenant_id == TENANT_A, "tenant must reach the transport for the JWT"
    body = transport.last_json_body["query"]
    assert body["measures"] == ["Sales.revenue_total"]
    assert body["dimensions"] == ["Sales.region"]
    assert body["timeDimensions"] == [
        {"dimension": "Sales.transaction_date", "granularity": "month"}
    ]
    assert body["order"] == {"Sales.revenue_total": "desc"}
    assert body["limit"] == 50


async def test_query_multi_metric_no_total(monkeypatch):
    client = _client()
    transport = FakeTransport(
        {
            "data": [{"Sales.revenue_total": 10, "Sales.units_sold": 2}],
            "annotation": {},
        }
    )
    monkeypatch.setattr(client, "_request", transport)

    result = await client.query(metrics=["Sales.revenue_total", "Sales.units_sold"])
    assert result.total is None
    assert result.metric_name == "multi"
