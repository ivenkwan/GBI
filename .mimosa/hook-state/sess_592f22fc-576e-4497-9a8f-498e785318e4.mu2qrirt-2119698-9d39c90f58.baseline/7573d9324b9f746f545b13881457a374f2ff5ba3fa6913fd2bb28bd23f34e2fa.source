"""API v1 router — aggregates all versioned route modules."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    byok,
    charts,
    chat,
    conversations,
    dashboards,
    datasources,
    health,
    lineage,
    metrics,
    reports,
    users,
    wiki,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(charts.router, prefix="/charts", tags=["charts"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(lineage.router, prefix="/lineage", tags=["lineage"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(wiki.router, prefix="/wiki", tags=["wiki"])
api_router.include_router(datasources.router, prefix="/datasources", tags=["datasources"])
api_router.include_router(byok.router, tags=["byok"])
