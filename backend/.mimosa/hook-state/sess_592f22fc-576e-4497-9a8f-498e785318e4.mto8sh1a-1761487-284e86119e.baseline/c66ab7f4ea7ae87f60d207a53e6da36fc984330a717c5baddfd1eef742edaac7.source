"""Phase 16 report tests: service pipeline + persistence contract.

All collaborators mocked: Cube client, LLM client, chart bridge, asyncpg.
"""

import json
from unittest.mock import AsyncMock, MagicMock

from app.services import reports as reports_service
from app.services.reports import (
    ReportGenerationError,
    _build_chart_spec,
    _plan_report,
    generate_report,
)

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"


def _patch_cube(monkeypatch, query_result=None, query_error=None):
    fake = MagicMock()
    fake.get_agent_context = AsyncMock(return_value="## Available Metrics\n- Sales.revenue_total")
    fake.query = AsyncMock(
        return_value=query_result,
        side_effect=query_error if query_error else None,
    )
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake)
    return fake


def _patch_llm(monkeypatch, plan=None, summary="Overall summary."):
    """Two sequential invokes: planner (parsed JSON) then summarizer (content)."""
    calls = []

    class FakeResult:
        def __init__(self, parsed, content):
            self.parsed = parsed
            self.content = content

    async def fake_invoke(**kwargs):
        calls.append(kwargs)
        if plan is not None and len(calls) == 1:
            return FakeResult(plan, json.dumps(plan))
        return FakeResult(None, summary)

    client = MagicMock()
    client.invoke = fake_invoke
    monkeypatch.setattr("app.core.llm_client.get_llm_client", lambda: client)
    return calls


def _patch_bridge(monkeypatch, svg="<svg>chart</svg>"):
    bridge = MagicMock()
    bridge.render = AsyncMock(return_value={"success": True, "svg": svg})
    monkeypatch.setattr(
        "app.agents.chart.flint_bridge.FlintChartBridge", MagicMock(return_value=bridge)
    )
    return bridge


def _patch_save(monkeypatch, returns=True):
    mock = AsyncMock(return_value=returns)
    monkeypatch.setattr(reports_service, "save_report", mock)
    return mock


def _query_result(rows):
    result = MagicMock()
    result.data = rows
    result.total = None
    return result


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


async def test_plan_report_parses_and_sanitizes(monkeypatch):
    _patch_cube(monkeypatch)
    calls = _patch_llm(
        monkeypatch,
        plan={
            "title": "Revenue report",
            "sections": [
                {
                    "metric": "Sales.revenue_total",
                    "title": "Revenue by Region",
                    "dimension": "Sales.region",
                },
                {"metric": "", "title": "bad — dropped"},  # no metric → dropped
                {"metric": "Orders.order_count", "title": "Orders"},
            ],
        },
    )

    plan = await _plan_report("revenue report", TENANT, USER, max_sections=3)

    assert plan["title"] == "Revenue report"
    assert len(plan["sections"]) == 2
    assert plan["sections"][0]["dimension"] == "Sales.region"
    # Planner call: temperature 0, JSON response format (deterministic plan)
    assert calls[0]["options"].response_format == "json"


async def test_plan_report_rejects_empty_plan(monkeypatch):
    _patch_cube(monkeypatch)
    _patch_llm(monkeypatch, plan={"title": "x", "sections": []})

    import pytest

    with pytest.raises(ReportGenerationError):
        await _plan_report("anything", TENANT, USER, max_sections=3)


# ---------------------------------------------------------------------------
# Chart spec (deterministic)
# ---------------------------------------------------------------------------


def test_bar_spec_for_categorical_slice():
    spec = _build_chart_spec(
        {"metric": "Sales.revenue_total"},
        [{"region": "North", "revenue_total": 100}, {"region": "South", "revenue_total": 50}],
    )
    assert spec["chartType"] == "Bar Chart"
    assert spec["encodings"]["x"]["field"] == "region"
    assert spec["encodings"]["y"]["field"] == "revenue_total"


def test_line_spec_for_time_granularity():
    spec = _build_chart_spec(
        {"metric": "Sales.revenue_total", "granularity": "month"},
        [{"month": "2026-01", "revenue_total": 100}],
    )
    assert spec["chartType"] == "Line Chart"
    assert spec["encodings"]["x"]["field"] == "month"


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


async def test_generate_report_happy_path(monkeypatch):
    fake_cube = _patch_cube(
        monkeypatch, query_result=_query_result([{"region": "North", "revenue_total": 100}])
    )
    _patch_llm(
        monkeypatch,
        plan={
            "title": "Q3 Report",
            "sections": [
                {"metric": "Sales.revenue_total", "title": "Revenue", "dimension": "Sales.region"}
            ],
        },
    )
    bridge = _patch_bridge(monkeypatch)
    save = _patch_save(monkeypatch, returns=True)

    report = await generate_report("Q3 revenue", TENANT, USER)

    # Tenant threading into the Cube query (RLS-correct data per ADR 008)
    assert fake_cube.query.call_args.kwargs["tenant_id"] == TENANT
    assert bridge.render.call_args.args[0]["chartType"] == "Bar Chart"

    assert report["title"] == "Q3 Report"
    assert report["summary"] == "Overall summary."
    assert report["sections"][0]["chart_svg"] == "<svg>chart</svg>"
    assert report["sections"][0]["data_total"] == 100  # single-metric total computed
    assert report["warnings"] == []
    save.assert_awaited_once()
    assert save.await_args.args[0]["report_id"] == report["report_id"]


async def test_failed_section_skipped_with_warning(monkeypatch):
    _patch_cube(monkeypatch, query_result=_query_result([]))  # no data → sections skip
    _patch_llm(
        monkeypatch,
        plan={
            "title": "T",
            "sections": [{"metric": "Sales.revenue_total", "title": "Revenue"}],
        },
    )
    _patch_bridge(monkeypatch)
    _patch_save(monkeypatch)

    import pytest

    with pytest.raises(ReportGenerationError):
        await generate_report("anything", TENANT, USER)


async def test_partial_failure_completes(monkeypatch):
    """One section errors, one succeeds → report completes with warning."""
    results = [
        ConnectionError("cube down"),  # first call raises...
        _query_result([{"region": "N", "order_count": 5}]),
    ]

    async def query_side_effect(**kwargs):
        item = results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    fake_cube = MagicMock()
    fake_cube.get_agent_context = AsyncMock(return_value="catalog")
    fake_cube.query = AsyncMock(side_effect=query_side_effect)
    monkeypatch.setattr("app.semantic.cube_client.get_cube_client", lambda: fake_cube)
    _patch_llm(
        monkeypatch,
        plan={
            "title": "T",
            "sections": [
                {"metric": "Sales.revenue_total", "title": "Revenue"},
                {"metric": "Orders.order_count", "title": "Orders"},
            ],
        },
    )
    _patch_bridge(monkeypatch)
    _patch_save(monkeypatch)

    report = await generate_report("mixed", TENANT, USER)

    assert len(report["sections"]) == 1
    assert report["sections"][0]["metric_name"] == "Orders.order_count"
    assert any("Sales.revenue_total" in w for w in report["warnings"])


async def test_persistence_failure_returns_report_with_warning(monkeypatch):
    _patch_cube(monkeypatch, query_result=_query_result([{"region": "N", "revenue_total": 1}]))
    _patch_llm(
        monkeypatch,
        plan={"title": "T", "sections": [{"metric": "Sales.revenue_total", "title": "R"}]},
    )
    _patch_bridge(monkeypatch)
    _patch_save(monkeypatch, returns=False)

    report = await generate_report("p", TENANT, USER)

    assert report["sections"]
    assert any("not saved" in w for w in report["warnings"])


# ---------------------------------------------------------------------------
# Persistence contract (mocked asyncpg)
# ---------------------------------------------------------------------------


def _patch_asyncpg(monkeypatch):
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    conn.close = AsyncMock()

    async def fake_connect(dsn=None, **kwargs):
        return conn

    monkeypatch.setattr(reports_service.asyncpg, "connect", fake_connect)
    return conn


def _report_dict():
    return {
        "report_id": "00000000-0000-0000-0000-0000000000cc",
        "title": "T",
        "prompt": "p",
        "summary": "s",
        "status": "complete",
        "sections": [
            {
                "position": 0,
                "metric_name": "Sales.revenue_total",
                "section_title": "Revenue",
                "chart_spec": {"chartType": "Bar Chart"},
                "chart_svg": "<svg/>",
                "data_total": 10.0,
                "row_count": 2,
                "narrative": None,
            }
        ],
    }


async def test_save_report_sets_guc_then_inserts(monkeypatch):
    conn = _patch_asyncpg(monkeypatch)

    ok = await reports_service.save_report(_report_dict(), TENANT, USER)

    assert ok is True
    guc_call = conn.execute.call_args_list[0]
    assert guc_call.args[1] == TENANT
    report_insert = conn.execute.call_args_list[1]
    assert report_insert.args[0].startswith("INSERT INTO reports")
    section_insert = conn.execute.call_args_list[2]
    assert section_insert.args[0].startswith("INSERT INTO report_sections")
    # chart_spec rides as a JSON string for the ::jsonb cast
    section_params = section_insert.args[1:]
    assert json.loads(section_params[5]) == {"chartType": "Bar Chart"}


async def test_save_report_fails_open(monkeypatch):
    conn = _patch_asyncpg(monkeypatch)
    conn.execute = AsyncMock(side_effect=ConnectionError("db down"))

    assert await reports_service.save_report(_report_dict(), TENANT, USER) is False


async def test_list_reports_scopes_to_user(monkeypatch):
    conn = _patch_asyncpg(monkeypatch)
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": "r1",
                "title": "T1",
                "created_at": MagicMock(isoformat=lambda: "2026-08-15T00:00:00+00:00"),
                "section_count": 2,
            }
        ]
    )

    rows = await reports_service.list_reports(USER, TENANT, limit=10)

    assert conn.fetch.call_args.args[1] == USER
    assert rows[0]["title"] == "T1"
    assert rows[0]["section_count"] == 2


async def test_get_report_not_found_returns_none(monkeypatch):
    conn = _patch_asyncpg(monkeypatch)
    conn.fetchrow = AsyncMock(return_value=None)

    assert await reports_service.get_report("00000000-0000-0000-0000-0000000000cc", TENANT) is None
