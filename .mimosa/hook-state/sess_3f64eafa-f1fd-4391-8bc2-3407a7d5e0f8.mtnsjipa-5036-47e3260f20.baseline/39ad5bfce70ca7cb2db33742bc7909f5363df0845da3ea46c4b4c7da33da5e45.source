"""Datasource endpoints — manage database connections."""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_datasources(
    user: dict = Depends(get_current_user),
):
    """List configured data sources for the current tenant."""
    return {"datasources": [], "status": "not_implemented"}


@router.post("/test")
async def test_connection(
    user: dict = Depends(get_current_user),
):
    """Test a database connection."""
    return {"status": "not_implemented"}
