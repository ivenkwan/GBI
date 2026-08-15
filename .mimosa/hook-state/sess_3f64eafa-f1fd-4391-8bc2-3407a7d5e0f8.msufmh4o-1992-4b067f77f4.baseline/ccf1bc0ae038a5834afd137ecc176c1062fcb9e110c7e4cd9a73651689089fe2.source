"""Report endpoints — assemble multi-chart reports with narrative."""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

router = APIRouter()


@router.post("/generate")
async def generate_report(
    user: dict = Depends(get_current_user),
):
    """Generate a report from a natural language prompt."""
    # TODO: implement report generation pipeline
    return {"status": "not_implemented", "message": "Report generation coming soon"}


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve a previously generated report."""
    return {"report_id": report_id, "status": "not_implemented"}
