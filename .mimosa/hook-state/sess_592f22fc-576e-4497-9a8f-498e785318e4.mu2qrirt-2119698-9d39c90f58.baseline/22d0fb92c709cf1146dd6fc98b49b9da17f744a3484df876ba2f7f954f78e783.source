"""AGE lineage service — records what every GenBI artifact touches (Phase 17).

`app/db/graph_schema.py` (Phase 15) parameterized its cypher but kept zero
callers. This service is the wiring: chat queries record the tables they
read (Table + USER_CAN_ACCESS), reports record the metrics they chart
(Metric), and dashboards record their pinned metric set (DASHBOARD_USES) —
which makes `get_table_impact` answer "what breaks if this table changes"
end to end.

How the AGE seam works (verified live against AGE 1.6):

- Every cypher statement lives in a SECURITY DEFINER SQL function created
  by ``infra/postgres/age-lineage.sql`` (fresh volumes get it from
  docker-entrypoint-initdb.d; existing databases run ``make
  lineage-setup``). AGE requires the cypher query text to be a constant
  and the params map to be a parameter, so the functions receive one
  ``agtype`` params argument and hand it straight to ``ag_catalog.cypher``
  as the third argument — the values never touch the query text.
- The runtime role (genbi_app) cannot ``LOAD 'age'`` (superuser-only), so
  the SQL file attaches ``session_preload_libraries = 'age'`` to the role
  itself.
- This module only ever executes static ``SELECT app_lineage.fn($1)``
  statements with the params map JSON-encoded as the single bound
  argument. No cypher in Python, nothing interpolated.
- Writers MERGE by natural key (``Table.name``, ``Metric.name``,
  ``Dashboard.id``) so recording is idempotent. graph_schema's uuid-keyed
  CREATE helpers remain the bulk-sync API for the nightly Cube ingestion.
- Writes are fail-open (False + warning) — a missing AGE extension or an
  unreachable graph must never break a query or a report. Reads raise so
  the API can answer honestly with 503 instead of "no impact".
"""

import json
import re
from datetime import UTC, datetime

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger

# ---------------------------------------------------------------------------
# SQL table extraction (for query lineage)
# ---------------------------------------------------------------------------

_SQL_COMMENT_RE = re.compile(r"(--[^\n]*)|(/\*.*?\*/)", re.DOTALL)
_CTE_NAME_RE = re.compile(r"(?:\bwith\b|,)\s*([A-Za-z_][\w$]*)\s+as\s*\(", re.IGNORECASE)
_FROM_CLAUSE_RE = re.compile(
    r"\bfrom\s+([^()]+?)(?=\bwhere\b|\bgroup\b|\border\b|\blimit\b|\bhaving\b"
    r"|\bjoin\b|\bunion\b|\bintersect\b|\bexcept\b|\bwindow\b|$)",
    re.IGNORECASE,
)
_JOIN_TARGET_RE = re.compile(
    r"\bjoin\s+([A-Za-z_][\w$]*(?:\s*\.\s*[A-Za-z_][\w$]*)?)", re.IGNORECASE
)
_RELATION_RE = re.compile(r"^[A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)?$")
# Words that can follow FROM/JOIN but never name a relation.
_NON_RELATION_WORDS = frozenset(
    {"select", "values", "unnest", "lateral", "generate_series", "only", "dual"}
)


def extract_tables(sql: str) -> list[str]:
    """Extract relation names from a read-only SELECT (FROM lists + JOINs).

    Handles schema-qualified names, aliases, comma-separated FROM lists, and
    skips CTE names (``WITH x AS (...)``) and function-call sources. Quoted
    identifiers are not supported — the generated analytical SQL this runs
    over is unquoted.
    """
    if not sql:
        return []

    cleaned = _SQL_COMMENT_RE.sub(" ", sql)
    cte_names = {m.group(1).lower() for m in _CTE_NAME_RE.finditer(cleaned)}

    candidates: list[str] = []

    # Scan the statement text twice: as-is (top-level FROM clauses) and with
    # parens replaced by spaces (FROMs inside subqueries/CTEs). The relation
    # filter below drops anything the paren pass picks up that isn't a name.
    for text in (cleaned, cleaned.replace("(", " ").replace(")", " ")):
        for m in _FROM_CLAUSE_RE.finditer(text):
            for part in m.group(1).split(","):
                words = part.strip().split(" ")
                # `FROM ONLY t` — skip the ONLY keyword
                if words and words[0].lower() == "only":
                    words = words[1:]
                if words:
                    candidates.append(words[0])

    for m in _JOIN_TARGET_RE.finditer(cleaned):
        candidates.append(m.group(1))

    tables: list[str] = []
    seen: set[str] = set()
    for cand in candidates:
        name = cand.replace(" ", "")
        if not _RELATION_RE.match(name):
            continue
        if name.lower() in _NON_RELATION_WORDS or name.lower() in cte_names:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            tables.append(name)
    return tables


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def _dsn() -> str:
    """asyncpg DSN for the runtime role (DATABASE_URL, plain driver)."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


# ---------------------------------------------------------------------------
# Lineage writers (fail-open)
# ---------------------------------------------------------------------------


async def record_query_lineage(tenant_id: str, user_id: str, roles: list[str], sql: str) -> bool:
    """Record the tables a chat query read + who read them. Fail-open."""
    tables = extract_tables(sql)
    if not tables:
        return True  # nothing to record is not a failure
    if user_id is None:
        user_id = ""

    granted = datetime.now(UTC).isoformat()
    try:
        conn = await asyncpg.connect(_dsn())
        try:
            async with conn.transaction():
                for table in tables:
                    table_params = json.dumps({"name": table})
                    await conn.execute(
                        "SELECT app_lineage.merge_table($1::ag_catalog.agtype)",
                        table_params,
                    )
                    access_params = json.dumps(
                        {
                            "uid": user_id,
                            "tenant": tenant_id,
                            "name": table,
                            "role": ",".join(roles) if roles else "user",
                            "granted": granted,
                        }
                    )
                    await conn.execute(
                        "SELECT app_lineage.merge_user_access($1::ag_catalog.agtype)",
                        access_params,
                    )
        finally:
            await conn.close()
        return True
    except Exception as e:  # noqa: BLE001 — lineage must never break a query
        logger.warning("Query lineage recording skipped (non-fatal): %s", e)
        return False


async def record_metrics_used(metrics: list[str]) -> bool:
    """Record the metrics a report's sections queried. Fail-open."""
    names = [m for m in dict.fromkeys(metrics) if m]
    if not names:
        return True

    try:
        conn = await asyncpg.connect(_dsn())
        try:
            async with conn.transaction():
                for name in names:
                    metric_params = json.dumps({"name": name})
                    await conn.execute(
                        "SELECT app_lineage.merge_metric($1::ag_catalog.agtype)",
                        metric_params,
                    )
        finally:
            await conn.close()
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Metric lineage recording skipped (non-fatal): %s", e)
        return False


async def record_dashboard_usage(
    dashboard_id: str, dashboard_name: str, metric_items: list[dict]
) -> bool:
    """Record/refresh a dashboard's DASHBOARD_USES edges. Fail-open.

    ``metric_items`` is ``[{"name": "Sales.revenue_total", "position": 0}, ...]``
    — the full pinned set. The refresh clears the dashboard's existing
    DASHBOARD_USES edges first, so unpinned metrics drop out atomically.
    """
    items = [
        {"name": str(i["name"]), "position": int(i.get("position", 0))}
        for i in metric_items
        if i.get("name")
    ]

    try:
        conn = await asyncpg.connect(_dsn())
        try:
            async with conn.transaction():
                dashboard_params = json.dumps({"id": dashboard_id, "name": dashboard_name})
                await conn.execute(
                    "SELECT app_lineage.upsert_dashboard($1::ag_catalog.agtype)",
                    dashboard_params,
                )
                clear_params = json.dumps({"id": dashboard_id})
                await conn.execute(
                    "SELECT app_lineage.clear_dashboard_edges($1::ag_catalog.agtype)",
                    clear_params,
                )
                for item in items:
                    edge_params = json.dumps(
                        {
                            "id": dashboard_id,
                            "metric": item["name"],
                            "position": item["position"],
                        }
                    )
                    await conn.execute(
                        "SELECT app_lineage.merge_dashboard_edge($1::ag_catalog.agtype)",
                        edge_params,
                    )
        finally:
            await conn.close()
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Dashboard lineage recording skipped (non-fatal): %s", e)
        return False


# ---------------------------------------------------------------------------
# Lineage readers (raise on failure — the API maps to 503)
# ---------------------------------------------------------------------------


def _parse_agtype(value) -> object:
    """agtype columns come back as JSON-encoded text; parse defensively."""
    if value is None:
        return None
    s = str(value)
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s.strip('"')


async def get_table_impact(table_name: str) -> list[dict]:
    """Downstream metrics + dashboards affected by a table change. Raises."""
    params = json.dumps({"name": table_name})
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name, metric_name, dashboards "
            "FROM app_lineage.table_impact($1::ag_catalog.agtype)",
            params,
        )
    finally:
        await conn.close()

    impact = []
    for row in rows:
        dashboards = _parse_agtype(row["dashboards"])
        if not isinstance(dashboards, list):
            dashboards = [dashboards] if dashboards else []
        impact.append(
            {
                "table": _parse_agtype(row["table_name"]) or table_name,
                "metric": _parse_agtype(row["metric_name"]),
                "dashboards": dashboards,
            }
        )
    return impact


async def get_metric_lineage(metric_name: str) -> dict:
    """A metric's source columns and the dashboards pinning it. Raises."""
    params = json.dumps({"name": metric_name})
    conn = await asyncpg.connect(_dsn())
    try:
        sources = await conn.fetch(
            "SELECT table_name, column_name FROM app_lineage.metric_sources($1::ag_catalog.agtype)",
            params,
        )
        dashboards = await conn.fetch(
            "SELECT dashboard_name FROM app_lineage.metric_dashboards($1::ag_catalog.agtype)",
            params,
        )
    finally:
        await conn.close()

    return {
        "metric": metric_name,
        "sources": [
            {
                "table": _parse_agtype(r["table_name"]),
                "column": _parse_agtype(r["column_name"]),
            }
            for r in sources
        ],
        "dashboards": [d for d in (_parse_agtype(r["dashboard_name"]) for r in dashboards) if d],
    }
