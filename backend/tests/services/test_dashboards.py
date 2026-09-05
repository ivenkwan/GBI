"""Phase 18 dashboard tests: service contract (faked asyncpg) + API matrix."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.services import dashboards as svc
from app.services.dashboards import (
    SectionNotFoundError,
    create_dashboard,
    delete_dashboard,
    get_dashboard,
    list_dashboards,
    pin_section,
    unpin_section,
)

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
REPORT = "00000000-0000-0000-0000-0000000000bb"
DASH = "00000000-0000-0000-0000-0000000000cc"
PIN = "00000000-0000-0000-0000-0000000000dd"


class FakeConn:
    def __init__(self):
        self.execute_calls = []
        self.fetchval_side_effect = None
        self.fetchrow_result = None
        self.fetch_result = []

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        if "DELETE FROM dashboards" in sql:
            return "DELETE 1"
        if "DELETE FROM dashboard_sections" in sql:
            return "DELETE 1"
        return "INSERT 0 1"

    async def fetchval(self, sql, *args):
        if self.fetchval_side_effect:
            return self.fetchval_side_effect(sql, args)
        if "coalesce(max(position)" in sql:
            return 0  # empty dashboard → first pin at position 0
        return 1  # section-exists check

    async def fetchrow(self, sql, *args):
        return self.fetchrow_result

    async def fetch(self, sql, *args):
        return self.fetch_result

    async def close(self):
        pass


@pytest.fixture
def fake_conn(monkeypatch):
    conn = FakeConn()

    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(svc.asyncpg, "connect", fake_connect)
    return conn


@pytest.fixture
def no_lineage(monkeypatch):
    """Pin/unpin lineage refresh — recorded as a call, never hits the graph."""
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.lineage.record_dashboard_usage", mock)
    return mock


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


async def test_create_dashboard_guc_and_insert(fake_conn):
    dashboard = await create_dashboard("Q3 Board", TENANT, USER, "desc")
    assert dashboard["dashboard_id"]
    guc = next(sql for sql, _ in fake_conn.execute_calls if "set_config" in sql)
    assert "app.current_tenant_id" in guc
    insert = next(sql for sql, _ in fake_conn.execute_calls if "INSERT INTO dashboards" in sql)
    assert "$1::uuid" in insert and "VALUES" in insert


async def test_list_dashboards_maps_rows(fake_conn):
    fake_conn.fetch_result = [
        {
            "id": DASH,
            "title": "Board",
            "description": None,
            "created_at": datetime(2026, 9, 5, tzinfo=UTC),
            "section_count": 2,
        }
    ]
    rows = await list_dashboards(USER, TENANT)
    assert rows[0]["id"] == DASH and rows[0]["section_count"] == 2


async def test_pin_section_validates_and_appends(fake_conn, no_lineage):
    fake_conn.fetchrow_result = {
        "id": DASH,
        "user_id": USER,
        "title": "Board",
        "description": None,
        "created_at": datetime(2026, 9, 5, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 5, tzinfo=UTC),
    }
    fake_conn.fetch_result = []  # get_dashboard pins: none
    pin = await pin_section(DASH, REPORT, 0, TENANT)
    assert pin["position"] == 0
    sqls = " ".join(sql for sql, _ in fake_conn.execute_calls)
    assert "INSERT INTO dashboard_sections" in sqls


async def test_pin_section_missing_section_raises(fake_conn):
    fake_conn.fetchval_side_effect = lambda sql, args: None
    with pytest.raises(SectionNotFoundError):
        await pin_section(DASH, REPORT, 9, TENANT)


async def test_unpin_missing_returns_false(fake_conn):
    conn = FakeConn()

    async def execute(sql, *args):
        return "DELETE 0" if "dashboard_sections" in sql else "UPDATE 1"

    conn.execute = execute

    async def fake_connect(_dsn):
        return conn

    import app.services.dashboards as svc_module

    orig = svc_module.asyncpg.connect
    svc_module.asyncpg.connect = fake_connect
    try:
        assert await unpin_section(DASH, PIN, TENANT) is False
    finally:
        svc_module.asyncpg.connect = orig


async def test_get_dashboard_resolves_pins_and_flags_dangling(fake_conn):
    fake_conn.fetchrow_result = {
        "id": DASH,
        "user_id": USER,
        "title": "Board",
        "description": None,
        "created_at": datetime(2026, 9, 5, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 5, tzinfo=UTC),
    }
    fake_conn.fetch_result = [
        {  # healthy pin
            "pin_id": PIN,
            "position": 0,
            "report_title": "R",
            "metric_name": "Sales.revenue_total",
            "section_title": "Revenue",
            "chart_spec": json.dumps({"chartType": "Bar Chart"}),
            "chart_svg": "<svg/>",
            "data_total": 5.0,
            "row_count": 2,
            "narrative": "ok",
        },
        {  # dangling pin (source section deleted)
            "pin_id": "00000000-0000-0000-0000-0000000000ee",
            "position": 1,
            "report_title": "R",
            "metric_name": None,
            "section_title": None,
            "chart_spec": None,
            "chart_svg": None,
            "data_total": None,
            "row_count": None,
            "narrative": None,
        },
    ]
    dashboard = await get_dashboard(DASH, TENANT)
    assert len(dashboard["sections"]) == 1
    assert dashboard["sections"][0]["chart_spec"] == {"chartType": "Bar Chart"}
    assert len(dashboard["warnings"]) == 1


async def test_pin_and_unpin_fire_lineage(fake_conn, monkeypatch, no_lineage):
    # get_dashboard is mocked whole — this test asserts the lineage hook,
    # not the pin-resolution query (covered by test_get_dashboard_*).
    detail = {
        "dashboard_id": DASH,
        "user_id": USER,
        "title": "Board",
        "description": None,
        "created_at": "2026-09-05T00:00:00+00:00",
        "updated_at": "2026-09-05T00:00:00+00:00",
        "sections": [],
        "warnings": [],
    }
    monkeypatch.setattr(svc, "get_dashboard", AsyncMock(return_value=detail))

    fake_conn.fetch_result = [{"metric_name": "Sales.revenue_total", "position": 0}]

    await pin_section(DASH, REPORT, 0, TENANT)
    no_lineage.assert_awaited_once()
    args = no_lineage.await_args[0]
    assert args[0] == DASH and args[1] == "Board"
    assert args[2] == [{"name": "Sales.revenue_total", "position": 0}]

    # unpin refreshes lineage too
    no_lineage.reset_mock()
    await unpin_section(DASH, PIN, TENANT)
    no_lineage.assert_awaited_once()


async def test_delete_dashboard(fake_conn):
    assert await delete_dashboard(DASH, TENANT) is True


# ---------------------------------------------------------------------------
# API
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


async def test_api_dashboard_crud_matrix(api_client, auth_headers, monkeypatch, no_lineage):
    detail = {
        "dashboard_id": DASH,
        "user_id": USER,
        "title": "Board",
        "description": None,
        "created_at": "2026-09-05T00:00:00+00:00",
        "updated_at": "2026-09-05T00:00:00+00:00",
        "sections": [],
        "warnings": [],
    }
    monkeypatch.setattr(
        "app.services.dashboards.create_dashboard",
        AsyncMock(
            return_value={
                "dashboard_id": DASH,
                "title": "Board",
                "description": None,
                "created_at": "2026-09-05T00:00:00+00:00",
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.dashboards.list_dashboards",
        AsyncMock(
            return_value=[
                {
                    "id": DASH,
                    "title": "Board",
                    "description": None,
                    "created_at": "2026-09-05T00:00:00+00:00",
                    "section_count": 0,
                }
            ]
        ),
    )
    monkeypatch.setattr("app.services.dashboards.get_dashboard", AsyncMock(return_value=detail))
    monkeypatch.setattr("app.services.dashboards.delete_dashboard", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "app.services.dashboards.pin_section",
        AsyncMock(return_value={"pin_id": PIN, "position": 0}),
    )
    monkeypatch.setattr("app.services.dashboards.unpin_section", AsyncMock(return_value=True))

    r = await api_client.post("/api/v1/dashboards", json={"title": "Board"}, headers=auth_headers)
    assert r.status_code == 201

    r = await api_client.get("/api/v1/dashboards", headers=auth_headers)
    assert r.status_code == 200 and r.json()["count"] == 1

    r = await api_client.get(f"/api/v1/dashboards/{DASH}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["dashboard_id"] == DASH

    r = await api_client.post(
        f"/api/v1/dashboards/{DASH}/sections",
        json={"report_id": REPORT, "section_position": 0},
        headers=auth_headers,
    )
    assert r.status_code == 201 and r.json()["pin_id"] == PIN

    r = await api_client.delete(f"/api/v1/dashboards/{DASH}/sections/{PIN}", headers=auth_headers)
    assert r.status_code == 200

    r = await api_client.delete(f"/api/v1/dashboards/{DASH}", headers=auth_headers)
    assert r.status_code == 200


async def test_api_dashboard_bad_uuid_and_missing(api_client, auth_headers, monkeypatch):
    r = await api_client.get("/api/v1/dashboards/not-a-uuid", headers=auth_headers)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "INVALID_DASHBOARD"

    monkeypatch.setattr("app.services.dashboards.get_dashboard", AsyncMock(return_value=None))
    r = await api_client.get(f"/api/v1/dashboards/{DASH}", headers=auth_headers)
    assert r.status_code == 404


async def test_api_pin_section_not_found(api_client, auth_headers, monkeypatch):
    async def raise_snf(**kwargs):
        raise SectionNotFoundError("no section")

    monkeypatch.setattr("app.services.dashboards.pin_section", raise_snf)
    r = await api_client.post(
        f"/api/v1/dashboards/{DASH}/sections",
        json={"report_id": REPORT, "section_position": 3},
        headers=auth_headers,
    )
    assert r.status_code == 404 and r.json()["detail"]["code"] == "SECTION_NOT_FOUND"
