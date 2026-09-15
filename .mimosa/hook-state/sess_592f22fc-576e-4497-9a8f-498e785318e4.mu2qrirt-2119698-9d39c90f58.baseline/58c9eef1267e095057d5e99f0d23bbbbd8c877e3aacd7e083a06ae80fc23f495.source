"""Phase 17 lineage tests: table extraction, fail-open writers, parsers.

All DB access is faked — no Postgres/AGE needed (CI runs without the AGE
image; the live-stack verification covers the real cypher path).
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import lineage
from app.services.lineage import (
    _parse_agtype,
    extract_tables,
    get_metric_lineage,
    get_table_impact,
    record_dashboard_usage,
    record_metrics_used,
    record_query_lineage,
)

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"


# ---------------------------------------------------------------------------
# extract_tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT * FROM sales", ["sales"]),
        ("SELECT * FROM public.sales WHERE x = 1", ["public.sales"]),
        (
            "SELECT r.region FROM public.sales r JOIN public.orders o ON o.region = r.region",
            ["public.sales", "public.orders"],
        ),
        # comma-separated FROM list
        ("SELECT * FROM sales, orders", ["sales", "orders"]),
        # alias handling
        ("SELECT * FROM sales s WHERE s.x = 1", ["sales"]),
        ("SELECT * FROM sales AS s", ["sales"]),
        # CTE names are skipped, referenced relations kept
        (
            "WITH totals AS (SELECT 1 FROM sales) SELECT * FROM totals JOIN orders ON true",
            ["sales", "orders"],
        ),
        # subquery / function source: no relation
        ("SELECT * FROM (SELECT 1) x", []),
        ("SELECT * FROM unnest(ARRAY[1,2])", []),
        # comments stripped
        ("SELECT 1 -- from fake_table\n", []),
        ("SELECT * /* from fake */ FROM sales", ["sales"]),
        # dedupe (case-insensitive)
        ("SELECT * FROM sales JOIN SALES ON true", ["sales"]),
        # keywords that follow FROM
        ("SELECT * FROM only sales", ["sales"]),
        ("", []),
    ],
)
def test_extract_tables(sql, expected):
    assert extract_tables(sql) == expected


def test_extract_tables_dedupes_identical_join():
    sql = "SELECT * FROM a JOIN b ON true JOIN a ON true"
    assert extract_tables(sql) == ["a", "b"]


# ---------------------------------------------------------------------------
# Writers: fail-open + binding contract
# ---------------------------------------------------------------------------


class FakeConn:
    """Records execute calls; raise_on toggles failure."""

    def __init__(self, raise_on=False):
        self.calls: list[tuple[str, object]] = []
        self.raise_on = raise_on

    async def execute(self, sql, *args):
        if self.raise_on:
            raise RuntimeError("age down")
        self.calls.append((sql, args))

    async def fetch(self, sql, *args):
        if self.raise_on:
            raise RuntimeError("age down")
        return []

    async def close(self):
        pass

    def transaction(self):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=None)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx


def _patch_connect(monkeypatch, conn: FakeConn):
    async def fake_connect(_dsn):
        return conn

    monkeypatch.setattr(lineage.asyncpg, "connect", fake_connect)
    return conn


async def test_record_query_lineage_binding_contract(monkeypatch):
    conn = _patch_connect(monkeypatch, FakeConn())
    ok = await record_query_lineage(
        TENANT,
        USER,
        ["user"],
        "SELECT * FROM public.sales JOIN public.orders ON true",
    )
    assert ok is True
    # 2 tables × 2 statements each (merge_table + merge_user_access)
    assert len(conn.calls) == 4
    sqls = " ".join(sql for sql, _ in conn.calls)
    # Values ride as the single bound parameter, never inside the SQL text
    assert "public.sales" not in sqls
    assert "$1::ag_catalog.agtype" in sqls
    assert all(len(args) == 1 for _, args in conn.calls)
    payloads = [json.loads(args[0]) for _, args in conn.calls]
    assert {"name": "public.sales"} in payloads
    access = next(p for p in payloads if "uid" in p)
    assert access["uid"] == USER and access["tenant"] == TENANT and access["role"] == "user"


async def test_record_query_lineage_no_tables_is_not_failure(monkeypatch):
    conn = _patch_connect(monkeypatch, FakeConn())
    assert await record_query_lineage(TENANT, USER, [], "SELECT 1") is True
    assert conn.calls == []


async def test_record_query_lineage_fail_open(monkeypatch):
    _patch_connect(monkeypatch, FakeConn(raise_on=True))
    assert await record_query_lineage(TENANT, USER, [], "SELECT * FROM sales") is False


async def test_record_metrics_used(monkeypatch):
    conn = _patch_connect(monkeypatch, FakeConn())
    assert await record_metrics_used(["Sales.revenue_total", "Sales.revenue_total", ""]) is True
    # dedupe + drop empties
    assert len(conn.calls) == 1
    assert json.loads(conn.calls[0][1][0]) == {"name": "Sales.revenue_total"}


async def test_record_metrics_used_fail_open(monkeypatch):
    _patch_connect(monkeypatch, FakeConn(raise_on=True))
    assert await record_metrics_used(["Sales.revenue_total"]) is False


async def test_record_dashboard_usage_clears_then_merges(monkeypatch):
    conn = _patch_connect(monkeypatch, FakeConn())
    ok = await record_dashboard_usage(
        "dash-1", "Q3", [{"name": "Sales.revenue_total", "position": 0}]
    )
    assert ok is True
    sqls = [sql for sql, _ in conn.calls]
    assert any("upsert_dashboard" in s for s in sqls)
    assert any("clear_dashboard_edges" in s for s in sqls)
    assert any("merge_dashboard_edge" in s for s in sqls)
    # no dashboard content interpolated into SQL
    assert "dash-1" not in " ".join(sqls)


# ---------------------------------------------------------------------------
# Readers: parse + raise-on-failure
# ---------------------------------------------------------------------------


async def test_get_table_impact_parses_agtype(monkeypatch):
    conn = FakeConn()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "table_name": '"public.sales"',
                "metric_name": '"Sales.revenue_total"',
                "dashboards": '["Q3", "Ops"]',
            },
        ]
    )
    _patch_connect(monkeypatch, conn)
    impact = await get_table_impact("public.sales")
    assert impact == [
        {
            "table": "public.sales",
            "metric": "Sales.revenue_total",
            "dashboards": ["Q3", "Ops"],
        }
    ]


async def test_get_metric_lineage_shape(monkeypatch):
    conn = FakeConn()

    async def fetch(sql, *args):
        if "metric_sources" in sql:
            return [{"table_name": '"public.sales"', "column_name": '"revenue"'}]
        return [{"dashboard_name": '"Q3"'}]

    conn.fetch = fetch
    _patch_connect(monkeypatch, conn)
    result = await get_metric_lineage("Sales.revenue_total")
    assert result == {
        "metric": "Sales.revenue_total",
        "sources": [{"table": "public.sales", "column": "revenue"}],
        "dashboards": ["Q3"],
    }


async def test_readers_raise_on_failure(monkeypatch):
    _patch_connect(monkeypatch, FakeConn(raise_on=True))
    with pytest.raises(RuntimeError):
        await get_table_impact("sales")
    with pytest.raises(RuntimeError):
        await get_metric_lineage("Sales.revenue_total")


def test_parse_agtype_defensive():
    assert _parse_agtype('"x"') == "x"
    assert _parse_agtype(None) is None
    assert _parse_agtype("0") == 0
    assert _parse_agtype("not json '") == "not json '"  # falls back to stripped text
