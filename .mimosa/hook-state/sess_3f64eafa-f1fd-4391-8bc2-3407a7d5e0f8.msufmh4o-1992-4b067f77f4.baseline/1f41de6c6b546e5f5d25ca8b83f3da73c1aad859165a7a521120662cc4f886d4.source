"""Metrics endpoints — query the semantic layer via Cube.dev."""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

router = APIRouter()


@router.get("/list")
async def list_metrics(
    user: dict = Depends(get_current_user),
):
    """List all available metrics from the semantic layer."""
    # TODO: query Cube.dev meta API or dbt manifest
    return {"metrics": [], "status": "not_implemented"}


@router.post("/query")
async def query_metrics(
    user: dict = Depends(get_current_user),
):
    """Execute a metric query against Cube.dev."""
    return {"data": [], "status": "not_implemented"}
