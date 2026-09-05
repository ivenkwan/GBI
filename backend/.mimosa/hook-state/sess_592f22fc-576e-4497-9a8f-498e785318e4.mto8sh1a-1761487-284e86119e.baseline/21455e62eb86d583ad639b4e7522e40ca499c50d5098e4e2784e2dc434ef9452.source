"""Report endpoints — assemble multi-chart reports with narrative (Phase 16)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter()


class ReportGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    max_sections: int = Field(default=3, ge=2, le=4)


class ReportSectionOut(BaseModel):
    position: int
    metric_name: str
    section_title: str
    chart_spec: dict
    chart_svg: str | None = None
    data_total: float | None = None
    row_count: int = 0
    narrative: str | None = None


class ReportOut(BaseModel):
    report_id: str
    title: str
    prompt: str
    summary: str | None = None
    status: str
    created_at: str
    sections: list[ReportSectionOut]
    warnings: list[str] = []


class ReportSummaryOut(BaseModel):
    id: str
    title: str
    created_at: str
    section_count: int


class ReportListResponse(BaseModel):
    reports: list[ReportSummaryOut]
    count: int


class ReportScheduleRequest(BaseModel):
    frequency: str = Field(pattern="^(hourly|daily|weekly|monthly)$")


class ReportScheduleOut(BaseModel):
    report_id: str
    frequency: str
    enabled: bool
    next_run_at: str
    last_run_at: str | None = None
    last_error: str | None = None


@router.post("/generate", response_model=ReportOut)
async def generate_report(
    request: ReportGenerateRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a multi-chart report from a natural language prompt.

    LLM-planned (metric selection from the semantic layer catalog) with
    deterministic execution: per-section tenant-scoped Cube query, chart
    render, and an overall narrative. Sections that return no data are
    skipped with a warning; the report persists best-effort.
    """
    from app.services.reports import ReportGenerationError, generate_report

    try:
        report = await generate_report(
            prompt=request.prompt,
            tenant_id=user["tenant_id"],
            user_id=user["sub"],
            max_sections=request.max_sections,
        )
    except ReportGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Could not plan a report for this prompt: {e}",
            },
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Report generation failed: {type(e).__name__}",
            },
        ) from None

    return ReportOut(**report)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List the current user's reports, newest first."""
    from app.services import reports as reports_service

    try:
        rows = await reports_service.list_reports(
            user_id=user["sub"], tenant_id=user["tenant_id"], limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Report store unavailable: {type(e).__name__}",
            },
        ) from None

    return ReportListResponse(reports=[ReportSummaryOut(**row) for row in rows], count=len(rows))


@router.post("/{report_id}/regenerate", response_model=ReportOut)
async def regenerate_report(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Re-run an existing report's pipeline on its stored prompt, in place
    (Phase 19). Sections are replaced; the report id is unchanged."""
    from app.services.reports import ReportGenerationError, regenerate_report

    try:
        uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPORT", "message": "Not a valid report id"},
        ) from None

    try:
        report = await regenerate_report(
            report_id=report_id,
            tenant_id=user["tenant_id"],
            user_id=user["sub"],
        )
    except ReportGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Could not regenerate the report: {e}",
            },
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Report regeneration failed: {type(e).__name__}",
            },
        ) from None

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": "No such report"},
        )

    return ReportOut(**report)


@router.post("/{report_id}/schedule", response_model=ReportScheduleOut)
async def schedule_report(
    report_id: str,
    request: ReportScheduleRequest,
    user: dict = Depends(get_current_user),
):
    """Create or replace the regeneration schedule for a report (Phase 19).

    The background scheduler (REPORT_SCHEDULER_ENABLED) regenerates due
    reports on their stored prompts.
    """
    from app.services import report_schedules as schedules

    try:
        uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPORT", "message": "Not a valid report id"},
        ) from None

    try:
        schedule = await schedules.schedule_report(
            report_id=report_id,
            frequency=request.frequency,
            tenant_id=user["tenant_id"],
            user_id=user["sub"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Schedule store unavailable: {type(e).__name__}",
            },
        ) from None

    return ReportScheduleOut(**schedule)


@router.get("/{report_id}/schedule", response_model=ReportScheduleOut)
async def get_report_schedule(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """The report's regeneration schedule, if any (Phase 19)."""
    from app.services import report_schedules as schedules

    try:
        uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPORT", "message": "Not a valid report id"},
        ) from None

    try:
        schedule = await schedules.get_schedule(report_id=report_id, tenant_id=user["tenant_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Schedule store unavailable: {type(e).__name__}",
            },
        ) from None

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHEDULE_NOT_FOUND", "message": "No schedule for this report"},
        )

    return ReportScheduleOut(**schedule)


@router.delete("/{report_id}/schedule")
async def unschedule_report(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Remove a report's regeneration schedule (Phase 19)."""
    from app.services import report_schedules as schedules

    try:
        uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPORT", "message": "Not a valid report id"},
        ) from None

    try:
        removed = await schedules.unschedule_report(
            report_id=report_id, tenant_id=user["tenant_id"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Schedule store unavailable: {type(e).__name__}",
            },
        ) from None

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHEDULE_NOT_FOUND", "message": "No schedule for this report"},
        )
    return {"status": "removed", "report_id": report_id}


@router.get("/{report_id}/pdf")
async def export_report_pdf(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Export a persisted report as a PDF (Phase 19).

    Text and layout always render; section charts rasterize when cairosvg
    is installed in the backend image, otherwise the chart slot carries a
    note.
    """
    from fastapi.responses import Response

    from app.services import reports as reports_service
    from app.services.report_pdf import render_report_pdf

    try:
        uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPORT", "message": "Not a valid report id"},
        ) from None

    try:
        report = await reports_service.get_report(report_id, tenant_id=user["tenant_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Report store unavailable: {type(e).__name__}",
            },
        ) from None

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": "No such report"},
        )

    pdf_bytes = render_report_pdf(report)
    filename = f"genbi-report-{report_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve a previously generated report (RLS tenant-scoped)."""
    from app.services import reports as reports_service

    try:
        uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REPORT", "message": "Not a valid report id"},
        ) from None

    try:
        report = await reports_service.get_report(report_id=report_id, tenant_id=user["tenant_id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Report store unavailable: {type(e).__name__}",
            },
        ) from None

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": "No such report"},
        )

    return ReportOut(**report)
