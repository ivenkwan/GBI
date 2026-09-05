"""Phase 17/20 wiring + endpoint tests: lineage hooks in the pipelines,
session_id in the sync response, new report endpoints, metric catalog cache."""

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.models.chat import ChatResponse

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
REPORT = "00000000-0000-0000-0000-0000000000bb"


# ---------------------------------------------------------------------------
# ChatService lineage wiring (reuses the Phase 13 pipeline fixtures)
# ---------------------------------------------------------------------------


async def test_chat_pipeline_records_lineage(monkeypatch):
    from app.services.chat_service import ChatService
    from tests.services.test_chat_pipeline import _patch_pipeline

    _patch_pipeline(
        monkeypatch,
        sql="SELECT region, SUM(revenue) FROM public.sales GROUP BY region",
    )

    recorder = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.lineage.record_query_lineage", recorder)

    service = ChatService(tenant_id=TENANT)
    response = await service.process_query(query="revenue by region", user_id=USER, roles=["user"])

    assert response["sql"]
    recorder.assert_awaited_once()
    kwargs = recorder.await_args[1]
    assert kwargs["tenant_id"] == TENANT and kwargs["user_id"] == USER
    assert "public.sales" in kwargs["sql"]


async def test_chat_pipeline_skips_lineage_when_no_data(monkeypatch):
    from app.services.chat_service import ChatService
    from tests.services.test_chat_pipeline import _patch_pipeline

    ctx = _patch_pipeline(monkeypatch)

    # Streaming path exits on no data BEFORE lineage runs.
    ctx["cache"].get_query_result = AsyncMock(return_value=[])

    recorder = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.lineage.record_query_lineage", recorder)

    service = ChatService(tenant_id=TENANT)
    events = []
    async for event in service.process_query_stream(
        query="revenue by region", user_id=USER, roles=["user"]
    ):
        events.append(event)

    assert any('"no_data"' in e for e in events)
    recorder.assert_not_awaited()


def test_sync_chat_response_carries_session_id():
    from app.services.chat_service import ChatService

    service = ChatService(tenant_id=TENANT)
    response = service._build_response(conversation_id=str(uuid.uuid4()), query="q")
    parsed = ChatResponse(**response)
    assert parsed.session_id == service.session_id


# ---------------------------------------------------------------------------
# Reports pipeline lineage wiring
# ---------------------------------------------------------------------------


async def test_report_generation_records_metrics(monkeypatch):
    from tests.services.test_reports import (
        _patch_bridge,
        _patch_cube,
        _patch_llm,
        _patch_save,
        _query_result,
    )

    _patch_cube(monkeypatch, query_result=_query_result([{"region": "North", "revenue_total": 5}]))
    _patch_llm(
        monkeypatch,
        plan={
            "title": "T",
            "sections": [{"metric": "Sales.revenue_total", "title": "Revenue"}],
        },
    )
    _patch_bridge(monkeypatch)
    _patch_save(monkeypatch)

    recorder = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.lineage.record_metrics_used", recorder)

    from app.services.reports import generate_report

    report = await generate_report("revenue", TENANT, USER)
    recorder.assert_awaited_once_with(["Sales.revenue_total"])
    assert report["report_id"]


async def test_regenerate_report_preserves_id(monkeypatch):
    from app.services import reports as reports_service
    from tests.services.test_reports import _patch_bridge, _patch_cube, _patch_llm, _query_result

    existing = {
        "report_id": REPORT,
        "prompt": "revenue please",
        "title": "T",
        "summary": "s",
        "status": "complete",
        "created_at": "2026-09-05T00:00:00+00:00",
        "sections": [],
        "warnings": [],
    }
    monkeypatch.setattr(reports_service, "get_report", AsyncMock(return_value=existing))
    monkeypatch.setattr(reports_service, "update_report", AsyncMock(return_value=True))
    _patch_cube(monkeypatch, query_result=_query_result([{"region": "North", "revenue_total": 5}]))
    _patch_llm(
        monkeypatch,
        plan={"title": "T2", "sections": [{"metric": "Sales.revenue_total", "title": "R"}]},
    )
    _patch_bridge(monkeypatch)
    monkeypatch.setattr("app.services.lineage.record_metrics_used", AsyncMock())

    regenerated = await reports_service.regenerate_report(REPORT, TENANT, USER)
    assert regenerated["report_id"] == REPORT
    assert "regenerated_at" in regenerated


async def test_regenerate_missing_report_returns_none(monkeypatch):
    from app.services import reports as reports_service

    monkeypatch.setattr(reports_service, "get_report", AsyncMock(return_value=None))
    assert await reports_service.regenerate_report(REPORT, TENANT, USER) is None


# ---------------------------------------------------------------------------
# New report API endpoints
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def api_client():
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id=USER, tenant_id=TENANT)
    return {"Authorization": f"Bearer {token}"}


async def test_regenerate_endpoint(api_client, auth_headers, monkeypatch):
    report = {
        "report_id": REPORT,
        "title": "T",
        "prompt": "p",
        "summary": "s",
        "status": "complete",
        "created_at": "2026-09-05T00:00:00+00:00",
        "sections": [],
        "warnings": [],
    }
    monkeypatch.setattr("app.services.reports.regenerate_report", AsyncMock(return_value=report))
    r = await api_client.post(f"/api/v1/reports/{REPORT}/regenerate", headers=auth_headers)
    assert r.status_code == 200 and r.json()["report_id"] == REPORT

    monkeypatch.setattr("app.services.reports.regenerate_report", AsyncMock(return_value=None))
    r = await api_client.post(f"/api/v1/reports/{REPORT}/regenerate", headers=auth_headers)
    assert r.status_code == 404

    r = await api_client.post("/api/v1/reports/nope/regenerate", headers=auth_headers)
    assert r.status_code == 400


async def test_schedule_endpoints(api_client, auth_headers, monkeypatch):
    from app.services import report_schedules as schedules

    schedule = {
        "report_id": REPORT,
        "frequency": "weekly",
        "enabled": True,
        "next_run_at": "2026-09-12T00:00:00+00:00",
        "last_run_at": None,
        "last_error": None,
    }
    monkeypatch.setattr(schedules, "schedule_report", AsyncMock(return_value=schedule))
    monkeypatch.setattr(schedules, "get_schedule", AsyncMock(return_value=schedule))
    monkeypatch.setattr(schedules, "unschedule_report", AsyncMock(return_value=True))

    r = await api_client.post(
        f"/api/v1/reports/{REPORT}/schedule", json={"frequency": "weekly"}, headers=auth_headers
    )
    assert r.status_code == 200 and r.json()["frequency"] == "weekly"

    r = await api_client.get(f"/api/v1/reports/{REPORT}/schedule", headers=auth_headers)
    assert r.status_code == 200

    r = await api_client.delete(f"/api/v1/reports/{REPORT}/schedule", headers=auth_headers)
    assert r.status_code == 200

    r = await api_client.post(
        f"/api/v1/reports/{REPORT}/schedule", json={"frequency": "yearly"}, headers=auth_headers
    )
    assert r.status_code == 422  # pydantic pattern rejects unknown frequencies


async def test_pdf_endpoint(api_client, auth_headers, monkeypatch):
    report = {
        "report_id": REPORT,
        "title": "T",
        "prompt": "p",
        "summary": None,
        "status": "complete",
        "created_at": "2026-09-05T00:00:00+00:00",
        "sections": [],
        "warnings": [],
    }
    monkeypatch.setattr("app.services.reports.get_report", AsyncMock(return_value=report))

    r = await api_client.get(f"/api/v1/reports/{REPORT}/pdf", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-1.4")
    assert "attachment" in r.headers["content-disposition"]

    monkeypatch.setattr("app.services.reports.get_report", AsyncMock(return_value=None))
    r = await api_client.get(f"/api/v1/reports/{REPORT}/pdf", headers=auth_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Lineage API
# ---------------------------------------------------------------------------


async def test_lineage_endpoints(api_client, auth_headers, monkeypatch):
    from app.services import lineage

    monkeypatch.setattr(
        lineage,
        "get_table_impact",
        AsyncMock(
            return_value=[
                {"table": "public.sales", "metric": "Sales.revenue_total", "dashboards": ["Q3"]}
            ]
        ),
    )
    r = await api_client.get("/api/v1/lineage/impact/public.sales", headers=auth_headers)
    assert r.status_code == 200 and r.json()["impacted"][0]["metric"] == "Sales.revenue_total"

    monkeypatch.setattr(
        lineage,
        "get_metric_lineage",
        AsyncMock(
            return_value={
                "metric": "Sales.revenue_total",
                "sources": [{"table": "public.sales", "column": "revenue"}],
                "dashboards": ["Q3"],
            }
        ),
    )
    r = await api_client.get("/api/v1/lineage/metric/Sales.revenue_total", headers=auth_headers)
    assert r.status_code == 200 and r.json()["dashboards"] == ["Q3"]

    # invalid names
    r = await api_client.get("/api/v1/lineage/impact/bad%20name", headers=auth_headers)
    assert r.status_code == 400

    # store down → 503
    async def boom(*a, **k):
        raise RuntimeError("age down")

    monkeypatch.setattr(lineage, "get_table_impact", boom)
    r = await api_client.get("/api/v1/lineage/impact/sales", headers=auth_headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "LINEAGE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Metric catalog cache (Phase 20)
# ---------------------------------------------------------------------------


def _metric_def(name):
    from app.semantic.cube_client import MetricDefinition, MetricType

    return MetricDefinition(
        name=name,
        title=name,
        description="d",
        metric_type=MetricType.SUM,
        cube_name=name.split(".")[0],
        measure_name=name.split(".")[1],
        dimensions=[],
        time_dimensions=[],
    )


async def test_metrics_list_uses_cache(api_client, auth_headers, monkeypatch):
    from tests.api.test_metrics import FakeCubeClient

    catalog = [
        {
            "name": "Sales.revenue_total",
            "title": "Sales.revenue_total",
            "description": "d",
            "metric_type": "sum",
            "cube_name": "Sales",
            "measure_name": "revenue_total",
            "dimensions": [],
            "time_dimensions": [],
        }
    ]

    calls = {"cube": 0}
    monkeypatch.setattr(
        "app.semantic.cube_client.get_cube_client",
        lambda: FakeCubeClient(metrics={"Sales.revenue_total": _metric_def("Sales.revenue_total")}),
    )

    cache = type("Cache", (), {})()
    cache.get_metric_catalog = AsyncMock(
        side_effect=lambda tenant: catalog if calls["cube"] > 0 else None
    )
    cache.set_metric_catalog = AsyncMock(side_effect=None)
    monkeypatch.setattr("app.core.cache.get_cache", lambda: cache)

    # First call: cache miss → Cube fetch → cache write
    original_list = FakeCubeClient.list_metrics

    async def counting_list(self, force_refresh=False):
        calls["cube"] += 1
        return await original_list(self, force_refresh)

    FakeCubeClient.list_metrics = counting_list
    try:
        r1 = await api_client.get("/api/v1/metrics/list", headers=auth_headers)
        assert r1.status_code == 200 and r1.json()["count"] == 1
        assert cache.set_metric_catalog.await_count == 1

        # Second call: served from cache (no additional Cube fetch)
        r2 = await api_client.get("/api/v1/metrics/list", headers=auth_headers)
        assert r2.status_code == 200
        assert calls["cube"] == 1
    finally:
        FakeCubeClient.list_metrics = original_list


async def test_metrics_list_serves_stale_on_outage(api_client, auth_headers, monkeypatch):
    class DeadCube:
        async def list_metrics(self, force_refresh=False):
            raise RuntimeError("cube down")

    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: DeadCube())

    stale = [
        {
            "name": "Sales.revenue_total",
            "title": "Sales.revenue_total",
            "description": "old",
            "metric_type": "sum",
            "cube_name": "Sales",
            "measure_name": "revenue_total",
            "dimensions": [],
            "time_dimensions": [],
        }
    ]
    cache = type("Cache", (), {})()
    # First lookup: miss (so Cube is tried). Second lookup: the stale
    # fallback after Cube fails.
    cache.get_metric_catalog = AsyncMock(side_effect=[None, stale])
    cache.set_metric_catalog = AsyncMock()
    monkeypatch.setattr("app.core.cache.get_cache", lambda: cache)

    r = await api_client.get("/api/v1/metrics/list", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["metrics"][0]["description"].startswith("[cached]")

    # No stale cache + outage → 503
    cache.get_metric_catalog = AsyncMock(return_value=None)
    r = await api_client.get("/api/v1/metrics/list", headers=auth_headers)
    assert r.status_code == 503


async def test_metrics_list_refresh_bypasses_cache(api_client, auth_headers, monkeypatch):
    from tests.api.test_metrics import FakeCubeClient

    monkeypatch.setattr(
        "app.semantic.cube_client.get_cube_client",
        lambda: FakeCubeClient(metrics={"Sales.revenue_total": _metric_def("Sales.revenue_total")}),
    )
    cache = type("Cache", (), {})()
    cache.get_metric_catalog = AsyncMock(return_value=None)
    cache.set_metric_catalog = AsyncMock()
    monkeypatch.setattr("app.core.cache.get_cache", lambda: cache)

    r = await api_client.get("/api/v1/metrics/list?refresh=true", headers=auth_headers)
    assert r.status_code == 200
    cache.get_metric_catalog.assert_not_awaited()
