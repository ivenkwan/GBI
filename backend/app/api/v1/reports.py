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
