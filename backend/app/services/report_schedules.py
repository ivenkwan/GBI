"""Report schedules — recurring regeneration of persisted reports (Phase 19).

One schedule per report. ``schedule_report`` upserts the row through the
RLS-bound runtime role (tenant GUC); ``run_due_schedules`` runs on the
owner role (DATABASE_URL_SYNC) whose ``scheduler_full`` policy (see
infra/postgres/rls/0007_report_schedules_rls.sql) lets it see due rows
across tenants. Each due schedule regenerates its report in place via
reports.regenerate_report and advances next_run_at — a failing report
never blocks the others (fail-open per schedule).

``scheduler_loop`` is the asyncio background task started by the app
lifespan when REPORT_SCHEDULER_ENABLED is set.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger

FREQUENCIES = ("hourly", "daily", "weekly", "monthly")


def _dsn() -> str:
    """asyncpg DSN for the runtime role (DATABASE_URL, plain driver)."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _owner_dsn() -> str:
    """asyncpg DSN for the owner role (DATABASE_URL_SYNC) — the scheduler
    path, which reads due rows across tenants."""
    url = make_url(settings.DATABASE_URL_SYNC)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _next_run(frequency: str, from_dt: datetime) -> datetime:
    """The next run anchor for a schedule.

    Deterministic and pure (unit-tested): hourly snaps to the top of the
    next hour; monthly approximates a calendar month as 30 days.
    """
    if frequency == "hourly":
        return from_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if frequency == "daily":
        return from_dt + timedelta(days=1)
    if frequency == "weekly":
        return from_dt + timedelta(weeks=1)
    return from_dt + timedelta(days=30)


# ---------------------------------------------------------------------------
# Schedule CRUD (runtime role, tenant GUC)
# ---------------------------------------------------------------------------


async def schedule_report(report_id: str, frequency: str, tenant_id: str, user_id: str) -> dict:
    """Create or replace the schedule for a report. Raises on DB failure."""
    freq = frequency.lower()
    if freq not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {FREQUENCIES}")

    now = datetime.now(UTC)
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
        row = await conn.fetchrow(
            "INSERT INTO report_schedules (report_id, tenant_id, user_id, frequency, next_run_at) VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5) ON CONFLICT (report_id) DO UPDATE SET frequency = $4, enabled = true, next_run_at = $5, updated_at = NOW() RETURNING report_id, frequency, enabled, next_run_at, last_run_at",
            report_id,
            tenant_id,
            user_id,
            freq,
            _next_run(freq, now),
        )
    finally:
        await conn.close()
    return {
        "report_id": str(row["report_id"]),
        "frequency": row["frequency"],
        "enabled": row["enabled"],
        "next_run_at": row["next_run_at"].isoformat(),
        "last_run_at": row["last_run_at"].isoformat() if row["last_run_at"] else None,
    }


async def unschedule_report(report_id: str, tenant_id: str) -> bool:
    """Disable + remove a report's schedule. False when none existed."""
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
        deleted = await conn.execute(
            "DELETE FROM report_schedules WHERE report_id = $1::uuid", report_id
        )
    finally:
        await conn.close()
    return deleted == "DELETE 1"


async def get_schedule(report_id: str, tenant_id: str) -> dict | None:
    """The report's schedule, or None. Raises on DB failure."""
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
        row = await conn.fetchrow(
            "SELECT report_id, frequency, enabled, next_run_at, last_run_at, last_error FROM report_schedules WHERE report_id = $1::uuid",
            report_id,
        )
    finally:
        await conn.close()
    if row is None:
        return None
    return {
        "report_id": str(row["report_id"]),
        "frequency": row["frequency"],
        "enabled": row["enabled"],
        "next_run_at": row["next_run_at"].isoformat(),
        "last_run_at": row["last_run_at"].isoformat() if row["last_run_at"] else None,
        "last_error": row["last_error"],
    }


# ---------------------------------------------------------------------------
# Due-run execution (owner role; fail-open per schedule)
# ---------------------------------------------------------------------------


async def run_due_schedules(now: datetime | None = None) -> int:
    """Regenerate every enabled schedule whose next_run_at is due.

    Returns the count of processed schedules (successes and failures —
    each failure is logged and recorded on the row, never raised).
    """
    from app.services.reports import regenerate_report

    now = now or datetime.now(UTC)
    processed = 0

    conn = await asyncpg.connect(_owner_dsn())
    try:
        due = await conn.fetch(
            "SELECT id, report_id, tenant_id, user_id, frequency FROM report_schedules WHERE enabled = true AND next_run_at <= $1 ORDER BY next_run_at LIMIT 20",
            now,
        )
    finally:
        await conn.close()

    for row in due:
        next_at = _next_run(row["frequency"], now)
        error = None
        try:
            await regenerate_report(
                report_id=str(row["report_id"]),
                tenant_id=str(row["tenant_id"]),
                user_id=str(row["user_id"]),
            )
        except Exception as e:  # noqa: BLE001 — one bad report never stops the rest
            error = f"{type(e).__name__}: {e}"[:500]
            logger.warning("Scheduled regeneration failed for report %s: %s", row["report_id"], e)

        mark_conn = await asyncpg.connect(_owner_dsn())
        try:
            await mark_conn.execute(
                "UPDATE report_schedules SET last_run_at = $2, next_run_at = $3, last_error = $4, updated_at = NOW() WHERE id = $1::uuid",
                row["id"],
                now,
                next_at,
                error,
            )
        finally:
            await mark_conn.close()
        processed += 1

    if due:
        logger.info("Scheduler pass: %d due schedule(s) processed", processed)
    return processed


async def scheduler_loop() -> None:
    """Background task: every REPORT_SCHEDULER_INTERVAL_SECONDS, run due
    schedules. Each tick fails open — a transient DB outage only logs."""
    interval = settings.REPORT_SCHEDULER_INTERVAL_SECONDS
    logger.info("Report scheduler enabled (interval=%ss)", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await run_due_schedules()
        except Exception as e:  # noqa: BLE001 — the loop must survive anything
            logger.warning("Scheduler tick failed (non-fatal): %s", e)
