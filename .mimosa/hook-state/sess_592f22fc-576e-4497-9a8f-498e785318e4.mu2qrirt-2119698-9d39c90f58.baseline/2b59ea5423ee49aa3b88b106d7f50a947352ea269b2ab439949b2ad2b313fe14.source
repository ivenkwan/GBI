"""Dashboard endpoints — pin report sections into persistent boards (Phase 18)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter()


class DashboardCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


class DashboardOut(BaseModel):
    dashboard_id: str
    title: str
    description: str | None = None
    created_at: str


class DashboardSectionOut(BaseModel):
    pin_id: str
    position: int
    report_title: str
    metric_name: str
    section_title: str
    chart_spec: dict
    chart_svg: str | None = None
    data_total: float | None = None
    row_count: int = 0
    narrative: str | None = None


class DashboardDetailOut(BaseModel):
    dashboard_id: str
    user_id: str
    title: str
    description: str | None = None
    created_at: str
    updated_at: str
    sections: list[DashboardSectionOut]
    warnings: list[str] = []


class DashboardSummaryOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    created_at: str
    section_count: int


class DashboardListResponse(BaseModel):
    dashboards: list[DashboardSummaryOut]
    count: int


class PinSectionRequest(BaseModel):
    report_id: str = Field(min_length=36, max_length=36)
    section_position: int = Field(ge=0, le=100)


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@router.post("", response_model=DashboardOut, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    request: DashboardCreateRequest,
    user: dict = Depends(get_current_user),
):
    """Create an empty dashboard. Pin report sections onto it afterwards."""
    from app.services import dashboards as service

    try:
        dashboard = await service.create_dashboard(
            title=request.title,
            description=request.description,
            tenant_id=user["tenant_id"],
            user_id=user["sub"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Dashboard store unavailable: {type(e).__name__}",
            },
        ) from None

    return DashboardOut(**dashboard)


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List the current user's dashboards, newest first."""
    from app.services import dashboards as service

    try:
        rows = await service.list_dashboards(
            user_id=user["sub"], tenant_id=user["tenant_id"], limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Dashboard store unavailable: {type(e).__name__}",
            },
        ) from None

    return DashboardListResponse(
        dashboards=[DashboardSummaryOut(**row) for row in rows], count=len(rows)
    )


@router.get("/{dashboard_id}", response_model=DashboardDetailOut)
async def get_dashboard(
    dashboard_id: str,
    user: dict = Depends(get_current_user),
):
    """One dashboard with pinned sections resolved to live chart data."""
    from app.services import dashboards as service

    if not _valid_uuid(dashboard_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DASHBOARD", "message": "Not a valid dashboard id"},
        )

    try:
        dashboard = await service.get_dashboard(
            dashboard_id=dashboard_id, tenant_id=user["tenant_id"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Dashboard store unavailable: {type(e).__name__}",
            },
        ) from None

    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DASHBOARD_NOT_FOUND", "message": "No such dashboard"},
        )

    return DashboardDetailOut(**dashboard)


@router.delete("/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a dashboard and its pins (source reports are untouched)."""
    from app.services import dashboards as service

    if not _valid_uuid(dashboard_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DASHBOARD", "message": "Not a valid dashboard id"},
        )

    try:
        deleted = await service.delete_dashboard(
            dashboard_id=dashboard_id, tenant_id=user["tenant_id"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Dashboard store unavailable: {type(e).__name__}",
            },
        ) from None

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DASHBOARD_NOT_FOUND", "message": "No such dashboard"},
        )
    return {"status": "deleted", "dashboard_id": dashboard_id}


@router.post(
    "/{dashboard_id}/sections",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def pin_section(
    dashboard_id: str,
    request: PinSectionRequest,
    user: dict = Depends(get_current_user),
):
    """Pin one report section onto the dashboard (appended last).

    Also refreshes the dashboard's DASHBOARD_USES lineage edges (fail-open).
    """
    from app.services import dashboards as service
    from app.services.dashboards import SectionNotFoundError

    if not _valid_uuid(dashboard_id) or not _valid_uuid(request.report_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ID", "message": "Not a valid dashboard/report id"},
        )

    try:
        pin = await service.pin_section(
            dashboard_id=dashboard_id,
            report_id=request.report_id,
            section_position=request.section_position,
            tenant_id=user["tenant_id"],
        )
    except SectionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SECTION_NOT_FOUND", "message": str(e)},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Dashboard store unavailable: {type(e).__name__}",
            },
        ) from None

    return pin


@router.delete("/{dashboard_id}/sections/{pin_id}")
async def unpin_section(
    dashboard_id: str,
    pin_id: str,
    user: dict = Depends(get_current_user),
):
    """Remove one pin from a dashboard."""
    from app.services import dashboards as service

    if not _valid_uuid(dashboard_id) or not _valid_uuid(pin_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ID", "message": "Not a valid dashboard/pin id"},
        )

    try:
        removed = await service.unpin_section(
            dashboard_id=dashboard_id, pin_id=pin_id, tenant_id=user["tenant_id"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PERSISTENCE_UNAVAILABLE",
                "message": f"Dashboard store unavailable: {type(e).__name__}",
            },
        ) from None

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PIN_NOT_FOUND", "message": "No such pinned section"},
        )
    return {"status": "removed", "pin_id": pin_id}
