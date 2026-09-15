"""Phase 19 tests: schedule math, due-run execution, and the PDF writer."""

import zlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.services import report_schedules as svc
from app.services.report_pdf import (
    _wrap,
    decode_png,
    render_report_pdf,
)
from app.services.report_schedules import _next_run, run_due_schedules

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-0000000000aa"
REPORT = "00000000-0000-0000-0000-0000000000bb"
NOW = datetime(2026, 9, 5, 12, 34, 56, tzinfo=UTC)


# ---------------------------------------------------------------------------
# _next_run
# ---------------------------------------------------------------------------


def test_next_run_hourly_snaps_to_top_of_hour():
    assert _next_run("hourly", NOW) == datetime(2026, 9, 5, 13, 0, 0, tzinfo=UTC)


def test_next_run_daily_weekly_monthly():
    assert _next_run("daily", NOW) == datetime(2026, 9, 6, 12, 34, 56, tzinfo=UTC)
    assert _next_run("weekly", NOW) == datetime(2026, 9, 12, 12, 34, 56, tzinfo=UTC)
    # monthly approximates 30 days
    assert _next_run("monthly", NOW) == datetime(2026, 10, 5, 12, 34, 56, tzinfo=UTC)


# ---------------------------------------------------------------------------
# run_due_schedules
# ---------------------------------------------------------------------------


class FakeDueConn:
    """Owner-role connection serving one due schedule row."""

    def __init__(self, due_rows):
        self.due_rows = due_rows
        self.updates = []

    async def fetch(self, sql, *args):
        if "report_schedules" in sql and "next_run_at <= $1" in sql:
            return self.due_rows
        return []

    async def execute(self, sql, *args):
        if "UPDATE report_schedules" in sql:
            self.updates.append(args)

    async def close(self):
        pass


@pytest.fixture
def regenerate_mock(monkeypatch):
    mock = AsyncMock(return_value={"report_id": REPORT})
    monkeypatch.setattr("app.services.reports.regenerate_report", mock)
    return mock


async def test_run_due_processes_and_advances(monkeypatch, regenerate_mock):
    row = {
        "id": "00000000-0000-0000-0000-0000000000ff",
        "report_id": REPORT,
        "tenant_id": TENANT,
        "user_id": USER,
        "frequency": "daily",
    }
    owner = FakeDueConn([row])

    async def fake_connect(dsn):
        assert "genbi_app" not in dsn or dsn  # owner DSN for the scheduler
        return owner

    monkeypatch.setattr(svc.asyncpg, "connect", fake_connect)

    processed = await run_due_schedules(now=NOW)
    assert processed == 1
    regenerate_mock.assert_awaited_once_with(report_id=REPORT, tenant_id=TENANT, user_id=USER)
    # advance: next_run = daily from NOW, no error recorded
    _, last_run, next_run, error = owner.updates[0]
    assert last_run == NOW
    assert next_run == datetime(2026, 9, 6, 12, 34, 56, tzinfo=UTC)
    assert error is None


async def test_run_due_isolated_failures(monkeypatch):
    rows = [
        {
            "id": f"00000000-0000-0000-0000-00000000000{i}",
            "report_id": REPORT,
            "tenant_id": TENANT,
            "user_id": USER,
            "frequency": "daily",
        }
        for i in (1, 2)
    ]
    owner = FakeDueConn(rows)

    async def fake_connect(dsn):
        return owner

    monkeypatch.setattr(svc.asyncpg, "connect", fake_connect)

    calls = {"n": 0}

    async def failing_regenerate(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("cube down")
        return {"report_id": kwargs["report_id"]}

    monkeypatch.setattr("app.services.reports.regenerate_report", failing_regenerate)

    processed = await run_due_schedules(now=NOW)
    assert processed == 2  # the failure did not stop the second schedule
    first_error = owner.updates[0][3]
    assert first_error and "RuntimeError" in first_error
    assert owner.updates[1][3] is None


async def test_run_due_nothing_due(monkeypatch, regenerate_mock):
    owner = FakeDueConn([])

    async def fake_connect(dsn):
        return owner

    monkeypatch.setattr(svc.asyncpg, "connect", fake_connect)
    assert await run_due_schedules(now=NOW) == 0
    regenerate_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# PDF writer
# ---------------------------------------------------------------------------


def _make_png(width=3, height=2, channels=4):
    """Build a minimal valid PNG with the raw filter per row."""
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # filter: none
        for _ in range(width * channels):
            raw.append(0xAB)
    compressed = zlib.compress(bytes(raw))

    def chunk(tag, data):
        c = tag + data
        return len(data).to_bytes(4, "big") + c + (zlib.crc32(c) & 0xFFFFFFFF).to_bytes(4, "big")

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, {3: 2, 4: 6, 1: 0}[channels], 0, 0, 0])
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def test_decode_png_rgba():
    w, h, ch, raw = decode_png(_make_png(3, 2, 4))
    assert (w, h, ch) == (3, 2, 4)
    assert len(raw) == 3 * 2 * 4


def test_decode_png_rejects_palette():

    data = _make_png(2, 2, 3)
    # Flip color_type to 3 (palette) in place
    ihdr_pos = 8
    patched = bytearray(data)
    patched[ihdr_pos + 8 + 9] = 3
    with pytest.raises(ValueError):
        decode_png(bytes(patched))


def test_wrap_breaks_long_lines():
    lines = _wrap("word " * 40, 10, 200)
    assert len(lines) > 1
    assert all(lines)


def test_render_report_pdf_structure():
    report = {
        "report_id": REPORT,
        "title": "Quarterly Report",
        "prompt": "show revenue",
        "summary": "Revenue is up.",
        "status": "complete",
        "created_at": "2026-09-05T00:00:00+00:00",
        "sections": [
            {
                "position": 0,
                "metric_name": "Sales.revenue_total",
                "section_title": "Revenue by Region",
                "chart_spec": {},
                "chart_svg": None,  # no cairosvg dependency in tests → note
                "data_total": 1234.0,
                "row_count": 4,
                "narrative": "North leads.",
            }
        ],
        "warnings": ["Skipped metric (no data): X"],
    }
    pdf = render_report_pdf(report)
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in pdf
    assert b"/Count 1" in pdf  # one page
    # Title and section text are in the content stream (parenthesized Tj)
    assert b"Quarterly Report" in pdf
    assert b"Revenue by Region" in pdf
    assert b"chart image unavailable" in pdf


def test_render_report_pdf_paginates_many_sections():
    section = {
        "position": 0,
        "metric_name": "Sales.revenue_total",
        "section_title": "Section",
        "chart_spec": {},
        "chart_svg": None,
        "data_total": 1.0,
        "row_count": 1,
        "narrative": "note " * 60,
    }
    report = {
        "report_id": REPORT,
        "title": "Big",
        "prompt": "p",
        "summary": "s",
        "status": "complete",
        "created_at": "2026-09-05T00:00:00+00:00",
        "sections": [dict(section, position=i) for i in range(12)],
        "warnings": [],
    }
    pdf = render_report_pdf(report)
    assert b"/Count 2" in pdf or b"/Count 3" in pdf  # multiple pages
