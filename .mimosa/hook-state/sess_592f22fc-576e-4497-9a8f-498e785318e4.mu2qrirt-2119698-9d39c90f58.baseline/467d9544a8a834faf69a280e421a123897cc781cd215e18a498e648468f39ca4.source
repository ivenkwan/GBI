"""Datasource endpoints — introspect the semantic layer's cubes."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import get_current_user

router = APIRouter()


class DatasourceSummary(BaseModel):
    name: str
    title: str
    measures: int
    dimensions: int


class DatasourceListResponse(BaseModel):
    datasources: list[DatasourceSummary]
    count: int


@router.get("", response_model=DatasourceListResponse)
async def list_datasources(
    user: dict = Depends(get_current_user),
):
    """List the semantic layer's cubes (data sources) for the current tenant."""
    from app.semantic.cube_client import get_cube_client

    try:
        meta = await get_cube_client().get_meta()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CUBE_UNAVAILABLE",
                "message": f"Semantic layer unavailable: {type(e).__name__}",
            },
        ) from None

    summaries = [
        DatasourceSummary(
            name=cube.get("name", ""),
            title=cube.get("title") or cube.get("name", ""),
            measures=len(cube.get("measures", [])),
            dimensions=len(cube.get("dimensions", [])),
        )
        for cube in meta.cubes
    ]

    return DatasourceListResponse(datasources=summaries, count=len(summaries))


@router.post("/test")
async def test_connection(
    user: dict = Depends(get_current_user),
):
    """Test a user-configured external database connection.

    Deliberately still a stub: this targets a different feature (admin-
    configured external warehouses), not the semantic layer's built-in
    Postgres source (which the readiness probe and /datasources cover).
    """
    return {"status": "not_implemented"}
