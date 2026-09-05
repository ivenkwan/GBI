"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Liveness probe — returns 200 if the server is running."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe — checks DB and Redis connectivity."""
    # TODO: actual DB/Redis ping
    return {
        "status": "ready",
        "database": "connected",
        "redis": "connected",
        "mcp_flint": "connected",
    }
