"""Report generation and persistence — multi-chart reports (Phase 16).

Pipeline (LLM-planned, deterministic execution — 2 LLM calls per report):
  1. Plan: one fast-model call over the metric catalog picks 2–4 sections
     (metric + slice dimension + title). Fail → REPORT_GENERATION_FAILED.
  2. Execute per section (fail-open): tenant-scoped Cube query →
     deterministic ChartAssemblyInput → FlintChartBridge SVG render.
  3. Summarize: one fast-model call over all section results.

Persistence follows the conversations.py pattern: asyncpg on the RLS-bound
runtime role with the tenant GUC per connection. Writes fail open (the
generated report returns even if persistence fails — with a warning);
reads raise so the API can map to 503/404.
"""

import contextlib
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


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


class ReportGenerationError(Exception):
    """Planning failed — no report could be produced."""


async def _plan_report(prompt: str, tenant_id: str, user_id: str, max_sections: int) -> dict:
    """LLM call 1: pick metrics + section structure from the catalog."""
    from app.core.llm_client import LLMCallOptions, get_llm_client, load_prompt
    from app.semantic.cube_client import get_cube_client

    catalog = await get_cube_client().get_agent_context(query=prompt)

    system = load_prompt("report-planner-system")
    user_message = (
        f"## Report Request\n\n{prompt}\n\n{catalog}\n\nPick at most {max_sections} sections."
    )

    client = get_llm_client()
    result = await client.invoke(
        messages=user_message,
        system=system,
        use_reasoning=False,
        options=LLMCallOptions(temperature=0.0, max_tokens=1024, response_format="json"),
        user_id=user_id,
        tenant_id=tenant_id,
        session_id=f"report-plan-{uuid.uuid4()}",
    )

    plan = result.parsed
    if not plan or not isinstance(plan.get("sections"), list) or not plan["sections"]:
        raise ReportGenerationError("planner returned no sections")

    # Sanitize: cap sections, truncate strings, drop unknown shapes.
    sections = []
    for raw in plan["sections"][:max_sections]:
        metric = str(raw.get("metric", "")).strip()
        if not metric:
            continue
        sections.append(
            {
                "metric": metric,
                "title": str(raw.get("title") or metric)[:200],
                "dimension": raw.get("dimension") or None,
                "granularity": raw.get("granularity") or None,
            }
        )
    if not sections:
        raise ReportGenerationError("planner returned no valid sections")

    return {"title": str(plan.get("title") or prompt)[:MAX_TITLE_LEN], "sections": sections}


def _build_chart_spec(section: dict, rows: list[dict]) -> dict:
    """Deterministic ChartAssemblyInput from a section plan + its rows."""
    metric_short = section["metric"].split(".")[-1]
    time_dim = section.get("granularity") is not None

    if time_dim and rows:
        # Trend: x = the time-granularity column, y = the metric
        x_field = next(
            (k for k in rows[0] if k.endswith(("_month", "_day")) or k in ("month", "day")),
            list(rows[0].keys())[0],
        )
        chart_type = "Line Chart"
    else:
        x_field = next(
            (k for k in rows[0] if k != metric_short),
            list(rows[0].keys())[0] if rows else "category",
        )
        chart_type = "Bar Chart"

    return {
        "chartType": chart_type,
        "encodings": {"x": {"field": x_field}, "y": {"field": metric_short}},
        "baseSize": {"width": 600, "height": 400},
        "data": {"values": rows},
    }


async def _execute_section(section: dict, tenant_id: str) -> dict | None:
    """Run the metric query + render the chart. Fail-open (None on error)."""
    from app.agents.chart.flint_bridge import FlintChartBridge
    from app.semantic.cube_client import get_cube_client

    try:
        cube = get_cube_client()
        time_dimensions = None
        dimensions = None
        if section.get("dimension") and section.get("granularity"):
            time_dimensions = [
                {"dimension": section["dimension"], "granularity": section["granularity"]}
            ]
        elif section.get("dimension"):
            dimensions = [section["dimension"]]

        result = await cube.query(
            metrics=[section["metric"]],
            dimensions=dimensions,
            time_dimensions=time_dimensions,
            limit=50,
            tenant_id=tenant_id,
        )
        if not result.data:
            return None

        spec = _build_chart_spec(section, result.data)

        svg = None
        try:
            bridge = FlintChartBridge(tenant_id=tenant_id)
            rendered = await bridge.render(spec, output_format="svg")
            if rendered.get("success"):
                svg = rendered.get("svg")
        except Exception as e:
            logger.warning("Report chart render failed (non-fatal): %s", e)

        total = result.total
        if total is None:
            with contextlib.suppress(Exception, KeyError, ValueError, TypeError):
                metric_short = section["metric"].split(".")[-1]
                nums = [
                    float(row[metric_short])
                    for row in result.data
                    if row.get(metric_short) is not None
                ]
                total = sum(nums) if nums else None

        return {
            "metric_name": section["metric"],
            "section_title": section["title"],
            "chart_spec": spec,
            "chart_svg": svg,
            "data_total": total,
            "row_count": len(result.data),
        }
    except Exception as e:
        logger.warning("Report section failed (skipped): %s — %s", section.get("metric"), e)
        return None


async def _summarize_report(prompt: str, title: str, sections: list[dict], tenant_id: str) -> str:
    """LLM call 2: one overall narrative from the section results."""
    from app.core.llm_client import get_llm_client, load_prompt

    lines = [f"Report: {title}", f"Request: {prompt}", "", "Sections:"]
    for s in sections:
        total = f"{s['data_total']:,.0f}" if s.get("data_total") is not None else "n/a"
        lines.append(f"- {s['section_title']}: {s['row_count']} rows, total {total}")

    result = await get_llm_client().invoke(
        messages="\n".join(lines),
        system=load_prompt("narrative-system"),
        use_reasoning=False,
        options=None,
        user_id=None,
        tenant_id=tenant_id,
    )
    return result.content


async def generate_report(prompt: str, tenant_id: str, user_id: str, max_sections: int = 3) -> dict:
    """Full pipeline: plan → execute sections → summarize. Returns the report
    dict (persisted best-effort — persistence failure adds a warning)."""
    plan = await _plan_report(prompt, tenant_id, user_id, max_sections)

    sections = []
    skipped = []
    for section in plan["sections"]:
        executed = await _execute_section(section, tenant_id)
        if executed is not None:
            executed["position"] = len(sections)
            sections.append(executed)
        else:
            skipped.append(section["metric"])

    if not sections:
        raise ReportGenerationError(
            f"all planned sections returned no data (metrics: "
            f"{', '.join(s['metric'] for s in plan['sections'])})"
        )

    summary = ""
    try:
        summary = await _summarize_report(prompt, plan["title"], sections, tenant_id)
    except Exception as e:
        logger.warning("Report summary failed (non-fatal): %s", e)

    report = {
        "report_id": str(uuid.uuid4()),
        "title": plan["title"],
        "prompt": prompt,
        "summary": summary,
        "status": "complete",
        "created_at": datetime.now(UTC).isoformat(),
        "sections": sections,
        "warnings": [f"Skipped metric (no data): {m}" for m in skipped],
    }

    persisted = await save_report(report, tenant_id, user_id)
    if not persisted:
        report["warnings"].append("Report could not be persisted — this copy is not saved")

    return report


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


async def save_report(report: dict, tenant_id: str, user_id: str) -> bool:
    """Persist report + sections. Fail-open (False on any problem)."""
    try:
        conn = await _connect(tenant_id)
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO reports (id, tenant_id, user_id, prompt, title, summary, status) "
                    "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7)",
                    report["report_id"],
                    tenant_id,
                    user_id,
                    report["prompt"],
                    report["title"],
                    report.get("summary") or None,
                    report.get("status", "complete"),
                )
                for section in report["sections"]:
                    await conn.execute(
                        "INSERT INTO report_sections "
                        "(report_id, tenant_id, position, metric_name, section_title, "
                        "chart_spec, chart_svg, data_total, row_count, narrative) "
                        "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7, $8, $9, $10)",
                        report["report_id"],
                        tenant_id,
                        section.get("position", 0),
                        section["metric_name"],
                        section["section_title"],
                        json.dumps(section["chart_spec"]),
                        section.get("chart_svg"),
                        section.get("data_total"),
                        section.get("row_count", 0),
                        section.get("narrative"),
                    )
        finally:
            await conn.close()
        return True
    except Exception as e:
        logger.warning("Report persistence failed (non-fatal): %s", e)
        return False


async def list_reports(user_id: str, tenant_id: str, limit: int = 50) -> list[dict]:
    """The user's reports, newest first. Raises on DB failure."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT r.id, r.title, r.created_at, "
            "(SELECT count(*) FROM report_sections s WHERE s.report_id = r.id) AS section_count "
            "FROM reports r WHERE r.user_id = $1::uuid "
            "ORDER BY r.created_at DESC LIMIT $2",
            user_id,
            limit,
        )
    finally:
        await conn.close()
    return [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "created_at": row["created_at"].isoformat(),
            "section_count": row["section_count"],
        }
        for row in rows
    ]


async def get_report(report_id: str, tenant_id: str) -> dict | None:
    """One persisted report with sections. None when not found. Raises on DB failure."""
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT id, user_id, prompt, title, summary, status, created_at "
            "FROM reports WHERE id = $1::uuid",
            report_id,
        )
        if row is None:
            return None

        section_rows = await conn.fetch(
            "SELECT position, metric_name, section_title, chart_spec, chart_svg, "
            "data_total, row_count, narrative "
            "FROM report_sections WHERE report_id = $1::uuid "
            "ORDER BY position",
            report_id,
        )
    finally:
        await conn.close()

    sections = []
    for s in section_rows:
        spec = s["chart_spec"]
        if isinstance(spec, str):
            spec = json.loads(spec)
        sections.append(
            {
                "position": s["position"],
                "metric_name": s["metric_name"],
                "section_title": s["section_title"],
                "chart_spec": spec or {},
                "chart_svg": s["chart_svg"],
                "data_total": s["data_total"],
                "row_count": s["row_count"],
                "narrative": s["narrative"],
            }
        )

    return {
        "report_id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "prompt": row["prompt"],
        "title": row["title"],
        "summary": row["summary"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
        "sections": sections,
        "warnings": [],
    }
