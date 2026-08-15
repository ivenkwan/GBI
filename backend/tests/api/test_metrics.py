"""API tests for /metrics/list and /metrics/query (Phases 9–10).

No database needed: auth uses locally-minted JWTs and the Cube client is
monkeypatched, so these run everywhere (CI without Cube included).
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.semantic.cube_client import (
    CubeMetaResponse,
    MetricDefinition,
    MetricQueryResult,
    MetricType,
)

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


class FakeCubeClient:
    def __init__(self, metrics=None, error=None, query_result=None, query_error=None):
        self._metrics = metrics or {}
        self._error = error
        self._query_result = query_result
        self._query_error = query_error
        self.last_query_tenant: str | None = None

    async def list_metrics(self, force_refresh: bool = False):
        if self._error:
            raise self._error
        return self._metrics

    async def get_meta(self, force_refresh: bool = False):
        if self._error:
            raise self._error
        return CubeMetaResponse(
            cubes=[
                {
                    "name": "Sales",
                    "title": "Sales",
                    "measures": [{"name": "revenue_total"}],
                    "dimensions": [{"name": "region"}],
                }
            ]
        )

    async def query(self, **kwargs):
        if self._query_error:
            raise self._query_error
        self.last_query_tenant = kwargs.get("tenant_id")
        return self._query_result


@pytest_asyncio.fixture
async def api_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id="test-user", tenant_id=DEFAULT_TENANT_ID)
    return {"Authorization": f"Bearer {token}"}


def _metric(name: str, cube: str, measure: str) -> MetricDefinition:
    return MetricDefinition(
        name=name,
        title=name,
        description=f"description of {name}",
        metric_type=MetricType.SUM,
        cube_name=cube,
        measure_name=measure,
        dimensions=["region"],
        time_dimensions=["transaction_date"],
    )


async def test_list_metrics_returns_catalog(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(
        metrics={
            "Sales.revenue_total": _metric("Sales.revenue_total", "Sales", "revenue_total"),
            # Alias entry sharing the same object — must be deduplicated.
            "revenue_total": _metric("Sales.revenue_total", "Sales", "revenue_total"),
            "Orders.order_count": _metric("Orders.order_count", "Orders", "order_count"),
        }
    )
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.get("/api/v1/metrics/list", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()

    names = [m["name"] for m in body["metrics"]]
    assert names == ["Sales.revenue_total", "Orders.order_count"]
    assert body["count"] == 2
    assert body["metrics"][0]["metric_type"] == "sum"


async def test_list_metrics_503_when_cube_down(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(error=ConnectionError("cube refused"))
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.get("/api/v1/metrics/list", headers=auth_headers)
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "CUBE_UNAVAILABLE"


async def test_list_metrics_requires_auth(api_client):
    res = await api_client.get("/api/v1/metrics/list")
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /metrics/query (Phase 10)
# ---------------------------------------------------------------------------

QUERY_RESULT = MetricQueryResult(
    metric_name="Sales.revenue_total",
    query={"measures": ["Sales.revenue_total"], "limit": 100},
    data=[{"revenue_total": 120000, "region": "North"}],
    annotation={"measures": {}},
    total=120000,
    query_latency_ms=12.5,
)


def _catalog() -> dict[str, MetricDefinition]:
    return {"Sales.revenue_total": _metric("Sales.revenue_total", "Sales", "revenue_total")}


async def test_query_metrics_happy_path_threads_tenant(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(metrics=_catalog(), query_result=QUERY_RESULT)
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.post(
        "/api/v1/metrics/query",
        json={"measures": ["Sales.revenue_total"], "dimensions": ["Sales.region"]},
        headers=auth_headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["data"] == [{"revenue_total": 120000, "region": "North"}]
    assert body["total"] == 120000
    assert body["cached"] is False

    # The JWT's tenant claim must reach CubeClient.query for the RLS GUC.
    assert fake.last_query_tenant == DEFAULT_TENANT_ID


async def test_query_metrics_second_call_served_from_cache(
    api_client, auth_headers, monkeypatch
):
    fake = FakeCubeClient(metrics=_catalog(), query_result=QUERY_RESULT)
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    first = await api_client.post(
        "/api/v1/metrics/query",
        json={"measures": ["Sales.revenue_total"]},
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["cached"] is False

    second = await api_client.post(
        "/api/v1/metrics/query",
        json={"measures": ["Sales.revenue_total"]},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert fake.last_query_tenant == DEFAULT_TENANT_ID  # only one live query


async def test_query_metrics_rejects_unknown_measure(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(metrics=_catalog())
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.post(
        "/api/v1/metrics/query",
        json={"measures": ["Sales.does_not_exist"]},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_METRIC"


async def test_query_metrics_503_when_cube_down(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(error=ConnectionError("cube refused"))
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.post(
        "/api/v1/metrics/query",
        json={"measures": ["Sales.revenue_total"]},
        headers=auth_headers,
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "CUBE_UNAVAILABLE"


async def test_query_metrics_validation_error(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(metrics=_catalog())
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.post(
        "/api/v1/metrics/query",
        json={"measures": []},
        headers=auth_headers,
    )
    assert res.status_code == 422


async def test_query_metrics_requires_auth(api_client):
    res = await api_client.post("/api/v1/metrics/query", json={"measures": ["x"]})
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /datasources (Phase 10)
# ---------------------------------------------------------------------------


async def test_list_datasources_returns_cubes(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient()
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.get("/api/v1/datasources", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["datasources"][0]["name"] == "Sales"
    assert body["datasources"][0]["measures"] == 1
    assert body["datasources"][0]["dimensions"] == 1


async def test_list_datasources_503_when_cube_down(api_client, auth_headers, monkeypatch):
    fake = FakeCubeClient(error=ConnectionError("cube refused"))
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)

    res = await api_client.get("/api/v1/datasources", headers=auth_headers)
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "CUBE_UNAVAILABLE"
