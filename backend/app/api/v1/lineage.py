"""Lineage endpoints — AGE impact analysis and metric lineage (Phase 17)."""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import get_current_user

router = APIRouter()

# Relation names may be schema-qualified; metric names are `cube.measure`.
_RELATION_NAME_RE = re.compile(r"^[A-Za-z_][\w$]*(\.[A-Za-z_][\w$]*)?$")
_METRIC_NAME_RE = re.compile(r"^[A-Za-z_][\w$]*(\.[A-Za-z_][\w$]*){0,3}$")


class ImpactEntry(BaseModel):
    table: str
    metric: str | None = None
    dashboards: list[str] = []


class ImpactResponse(BaseModel):
    table: str
    impacted: list[ImpactEntry]


class MetricSource(BaseModel):
    table: str | None = None
    column: str | None = None


class MetricLineageResponse(BaseModel):
    metric: str
    sources: list[MetricSource]
    dashboards: list[str]


@router.get("/impact/{table_name}", response_model=ImpactResponse)
async def table_impact(
    table_name: str,
    user: dict = Depends(get_current_user),
):
    """Downstream metrics and dashboards affected by a change to a table.

    Reads the AGE lineage graph: Table → Column ← METRIC_SOURCE ← Metric ←
    DASHBOARD_USES ← Dashboard. Note METRIC_SOURCE edges come from the
    semantic-layer sync; tables whose metrics were never ingested report no
    impact.
    """
    from app.services import lineage

    if not _RELATION_NAME_RE.match(table_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_NAME", "message": "Not a valid table name"},
        )

    try:
        impact = await lineage.get_table_impact(table_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "LINEAGE_UNAVAILABLE",
                "message": f"Lineage graph unavailable: {type(e).__name__}",
            },
        ) from None

    return ImpactResponse(table=table_name, impacted=[ImpactEntry(**entry) for entry in impact])


@router.get("/metric/{metric_name}", response_model=MetricLineageResponse)
async def metric_lineage(
    metric_name: str,
    user: dict = Depends(get_current_user),
):
    """A metric's source columns and the dashboards pinning it."""
    from app.services import lineage

    if not _METRIC_NAME_RE.match(metric_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_NAME", "message": "Not a valid metric name"},
        )

    try:
        result = await lineage.get_metric_lineage(metric_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "LINEAGE_UNAVAILABLE",
                "message": f"Lineage graph unavailable: {type(e).__name__}",
            },
        ) from None

    return MetricLineageResponse(
        metric=metric_name,
        sources=[MetricSource(**s) for s in result["sources"]],
        dashboards=result["dashboards"],
    )
