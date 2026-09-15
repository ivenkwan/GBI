"""Dashboard persistence — pin report sections onto a board (Phase 18).

Follows the conversations/reports pattern: asyncpg on the RLS-bound runtime
role with the tenant GUC per connection. A dashboard pins *sections of
existing reports* (report_id + section_position), so the chart and metric
travel together and stay in sync with the report.

Every pin/unpin also refreshes the dashboard's DASHBOARD_USES lineage
edges in the AGE graph (fail-open — the dashboard itself never depends on
the graph being reachable).
"""

import json
import uuid
from datetime import UTC, datetime

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger

MAX_TITLE_LEN = 500


def _dsn() -> str:
    """asyncpg DSN for the runtime role (DATABASE_URL, plain driver)."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _connect(tenant_id: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
    return conn


async def _refresh_lineage(dashboard_id: str, title: str, tenant_id: str) -> None:
    """Record the dashboard's pinned metrics as DASHBOARD_USES edges."""
    try:
        from app.services.lineage import record_dashboard_usage

        metrics = await dashboard_metrics(dashboard_id, tenant_id)
        await record_dashboard_usage(dashboard_id, title, metrics)
    except Exception as e:  # noqa: BLE001
        logger.warning("Dashboard lineage refresh skipped (non-fatal): %s", e)


async def dashboard_metrics(dashboard_id: str, tenant_id: str) -> list[dict]:
    """The dashboard's pinned metric names + positions (for lineage)."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT rs.metric_name, ds.position FROM dashboard_sections ds "
            "JOIN report_sections rs ON rs.report_id = ds.report_id "
            "AND rs.position = ds.section_position "
            "WHERE ds.dashboard_id = $1::uuid ORDER BY ds.position",
            dashboard_id,
        )
    finally:
        await conn.close()
    return [{"name": row["metric_name"], "position": row["position"]} for row in rows]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_dashboard(
    title: str, tenant_id: str, user_id: str, description: str | None = None
) -> dict:
    """Create an empty dashboard. Raises on DB failure."""
    dashboard_id = str(uuid.uuid4())
    safe_title = title[:MAX_TITLE_LEN]
    conn = await _connect(tenant_id)
    try:
        await conn.execute(
            "INSERT INTO dashboards (id, tenant_id, user_id, title, description) VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5)",
            dashboard_id,
            tenant_id,
            user_id,
            safe_title,
            description,
        )
    finally:
        await conn.close()
    return {
        "dashboard_id": dashboard_id,
        "title": safe_title,
        "description": description,
        "section_count": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def list_dashboards(user_id: str, tenant_id: str, limit: int = 50) -> list[dict]:
    """The user's dashboards, newest first. Raises on DB failure."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT d.id, d.title, d.description, d.created_at, "
            "(SELECT count(*) FROM dashboard_sections s WHERE s.dashboard_id = d.id) "
            "AS section_count "
            "FROM dashboards d WHERE d.user_id = $1::uuid "
            "ORDER BY d.created_at DESC LIMIT $2",
            user_id,
            limit,
        )
    finally:
        await conn.close()
    return [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "created_at": row["created_at"].isoformat(),
            "section_count": row["section_count"],
        }
        for row in rows
    ]


class SectionNotFoundError(Exception):
    """The report section being pinned does not exist."""


async def pin_section(
    dashboard_id: str, report_id: str, section_position: int, tenant_id: str
) -> dict:
    """Pin one report section onto a dashboard (appended last). Raises
    SectionNotFoundError when the report section does not exist; DB errors raise."""
    conn = await _connect(tenant_id)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM report_sections WHERE report_id = $1::uuid AND position = $2",
            report_id,
            section_position,
        )
        if not exists:
            raise SectionNotFoundError(
                f"report {report_id} has no section at position {section_position}"
            )

        next_position = await conn.fetchval(
            "SELECT coalesce(max(position) + 1, 0) FROM dashboard_sections "
            "WHERE dashboard_id = $1::uuid",
            dashboard_id,
        )
        pin_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO dashboard_sections (id, dashboard_id, tenant_id, report_id, section_position, position) VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6)",
            pin_id,
            dashboard_id,
            tenant_id,
            report_id,
            section_position,
            next_position,
        )
        await conn.execute(
            "UPDATE dashboards SET updated_at = NOW() WHERE id = $1::uuid",
            dashboard_id,
        )
    finally:
        await conn.close()

    dashboard = await get_dashboard(dashboard_id, tenant_id)
    await _refresh_lineage(dashboard_id, dashboard["title"], tenant_id)

    return {"pin_id": pin_id, "position": next_position}


async def unpin_section(dashboard_id: str, pin_id: str, tenant_id: str) -> bool:
    """Remove a pin. False when the pin does not exist. Raises on DB failure."""
    conn = await _connect(tenant_id)
    try:
        deleted = await conn.execute(
            "DELETE FROM dashboard_sections WHERE dashboard_id = $1::uuid AND id = $2::uuid",
            dashboard_id,
            pin_id,
        )
        if deleted != "DELETE 1":
            return False
        await conn.execute(
            "UPDATE dashboards SET updated_at = NOW() WHERE id = $1::uuid",
            dashboard_id,
        )
    finally:
        await conn.close()

    dashboard = await get_dashboard(dashboard_id, tenant_id)
    await _refresh_lineage(dashboard_id, dashboard["title"], tenant_id)
    return True


async def get_dashboard(dashboard_id: str, tenant_id: str) -> dict | None:
    """One dashboard with its pinned sections resolved to chart data.

    Sections whose source report/section no longer exists are skipped with
    a warning entry. None when the dashboard is not found. Raises on DB
    failure.
    """
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT id, user_id, title, description, created_at, updated_at "
            "FROM dashboards WHERE id = $1::uuid",
            dashboard_id,
        )
        if row is None:
            return None
        pin_rows = await conn.fetch(
            "SELECT ds.id AS pin_id, ds.position, r.title AS report_title, "
            "rs.position AS section_position, rs.metric_name, rs.section_title, "
            "rs.chart_spec, rs.chart_svg, rs.data_total, rs.row_count, rs.narrative "
            "FROM dashboard_sections ds "
            "JOIN reports r ON r.id = ds.report_id "
            "LEFT JOIN report_sections rs ON rs.report_id = ds.report_id "
            "AND rs.position = ds.section_position "
            "WHERE ds.dashboard_id = $1::uuid ORDER BY ds.position",
            dashboard_id,
        )
    finally:
        await conn.close()

    sections = []
    warnings = []
    for pin in pin_rows:
        if pin["metric_name"] is None:
            warnings.append(
                f"Pinned section no longer exists (report section dropped); pin {pin['pin_id']}"
            )
            continue
        spec = pin["chart_spec"]
        if isinstance(spec, str):
            spec = json.loads(spec)
        sections.append(
            {
                "pin_id": str(pin["pin_id"]),
                "position": pin["position"],
                "report_title": pin["report_title"],
                "metric_name": pin["metric_name"],
                "section_title": pin["section_title"],
                "chart_spec": spec or {},
                "chart_svg": pin["chart_svg"],
                "data_total": pin["data_total"],
                "row_count": pin["row_count"],
                "narrative": pin["narrative"],
            }
        )

    return {
        "dashboard_id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "title": row["title"],
        "description": row["description"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "sections": sections,
        "warnings": warnings,
    }


async def delete_dashboard(dashboard_id: str, tenant_id: str) -> bool:
    """Delete a dashboard (pins cascade). False when not found. Raises on
    DB failure."""
    conn = await _connect(tenant_id)
    try:
        deleted = await conn.execute("DELETE FROM dashboards WHERE id = $1::uuid", dashboard_id)
    finally:
        await conn.close()
    return deleted == "DELETE 1"
