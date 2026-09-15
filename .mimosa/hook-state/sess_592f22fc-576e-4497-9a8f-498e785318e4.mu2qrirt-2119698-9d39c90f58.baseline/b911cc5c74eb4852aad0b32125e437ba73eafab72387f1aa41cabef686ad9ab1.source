"""Admin endpoints — platform control plane (Phase 21, ADR 009 §6).

All routes are guarded by ``require_platform_admin`` (JWT claim + cached
grant re-check) and every mutation is audited by the service layer.
"""

import json
import re
import secrets
import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import _admin_dsn, require_platform_admin

router = APIRouter()

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TenantProvisionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=3, max_length=50)
    admin_email: str = Field(min_length=3, max_length=255)
    # Optional explicit password; when absent a random one is generated and
    # returned exactly once (never stored in plaintext anywhere).
    admin_password: str | None = Field(default=None, min_length=8, max_length=128)
    seed_sample_data: bool = False


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, pattern="^(active|suspended)$")
    settings: dict | None = None


class AdminGrantRequest(BaseModel):
    user_id: str | None = Field(default=None, min_length=36, max_length=36)
    email: str | None = Field(default=None, max_length=255)


class TenantSummaryOut(BaseModel):
    id: str
    name: str
    slug: str | None = None
    status: str
    created_at: str
    user_count: int


class TenantListResponse(BaseModel):
    tenants: list[TenantSummaryOut]
    count: int


class ProvisionOut(BaseModel):
    tenant_id: str
    name: str
    slug: str
    status: str
    admin_user_id: str
    admin_email: str
    seeded: bool
    created_at: str
    # One-time display of the generated password (absent when caller set it)
    temp_password: str | None = None


class TenantUserOut(BaseModel):
    id: str
    email: str
    roles: list[str]
    created_at: str


class TenantDetailOut(BaseModel):
    id: str
    name: str
    slug: str | None = None
    status: str
    settings: dict = {}
    created_at: str
    updated_at: str
    user_count: int
    users: list[TenantUserOut]
    counters: dict
    recent_admin_actions: list[dict]


class PlatformStatsOut(BaseModel):
    tenants_total: int
    tenants_active: int
    tenants_suspended: int
    users_total: int
    llm_calls_24h: int
    llm_tokens_24h: int = 0
    llm_byok_calls_24h: int = 0
    platform_admins_active: int


class SuperadminOut(BaseModel):
    user_id: str
    email: str | None = None
    granted_by: str | None = None
    granted_at: str
    revoked_by: str | None = None
    revoked_at: str | None = None
    active: bool


class AdminAuditOut(BaseModel):
    actor_user_id: str
    action: str
    target_type: str
    target_id: str | None = None
    detail: dict | None = None
    created_at: str


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@router.get("/stats", response_model=PlatformStatsOut)
async def get_platform_stats(user: dict = Depends(require_platform_admin)):
    """Platform counters: tenants by status, users, LLM calls (24h)."""
    from app.services.tenants import platform_stats

    try:
        return PlatformStatsOut(**await platform_stats())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(user: dict = Depends(require_platform_admin)):
    """Tenant list with user counts, newest first."""
    from app.services import tenants as service

    try:
        rows = await service.list_tenants()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None
    return TenantListResponse(tenants=[TenantSummaryOut(**r) for r in rows], count=len(rows))


@router.post("/tenants", response_model=ProvisionOut, status_code=status.HTTP_201_CREATED)
async def provision_tenant(
    request: TenantProvisionRequest,
    user: dict = Depends(require_platform_admin),
):
    """Provision a tenant + initial admin user (transactional).

    When ``admin_password`` is absent, a random one is generated and
    returned exactly once — it is never stored or logged anywhere.
    """
    from app.services.tenants import TenantExistsError, UserExistsError, provision_tenant

    if not _SLUG_RE.match(request.slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SLUG",
                "message": "Slug must be 3-50 chars: lowercase letters, digits, hyphens",
            },
        )
    if not _EMAIL_RE.match(request.admin_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_EMAIL", "message": "Not a valid admin email"},
        )

    temp_password = request.admin_password or secrets.token_urlsafe(12)
    try:
        result = await provision_tenant(
            name=request.name,
            slug=request.slug,
            admin_email=request.admin_email,
            admin_password=temp_password,
            actor_user_id=str(user["sub"]),
            seed_sample_data=request.seed_sample_data,
        )
    except TenantExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TENANT_EXISTS", "message": str(e)},
        ) from None
    except UserExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "USER_EXISTS", "message": str(e)},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Provisioning failed: {type(e).__name__}",
            },
        ) from None

    return ProvisionOut(
        **result,
        temp_password=temp_password if request.admin_password is None else None,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantDetailOut)
async def get_tenant(
    tenant_id: str,
    user: dict = Depends(require_platform_admin),
):
    """Tenant detail: users, business counters, recent admin actions."""
    from app.services.tenants import get_tenant as get_detail

    if not _valid_uuid(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TENANT", "message": "Not a valid tenant id"},
        )
    try:
        detail = await get_detail(tenant_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TENANT_NOT_FOUND", "message": "No such tenant"},
        )
    return TenantDetailOut(**detail)


@router.patch("/tenants/{tenant_id}", response_model=TenantDetailOut)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdateRequest,
    user: dict = Depends(require_platform_admin),
):
    """Rename / suspend / activate / merge settings (audited)."""
    from app.services.tenants import update_tenant as update

    if not _valid_uuid(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TENANT", "message": "Not a valid tenant id"},
        )
    try:
        detail = await update(
            tenant_id=tenant_id,
            actor_user_id=str(user["sub"]),
            name=request.name,
            status=request.status,
            settings_patch=request.settings,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TENANT_NOT_FOUND", "message": "No such tenant"},
        )
    return TenantDetailOut(**detail)


@router.delete("/tenants/{tenant_id}")
async def decommission_tenant(
    tenant_id: str,
    user: dict = Depends(require_platform_admin),
    confirm: str = Query(default="", description="Must be 'yes' — decommission is destructive"),
    force: bool = Query(default=False, description="Delete even when users exist"),
):
    """Decommission a tenant (destructive, guarded, audited).

    Requires ``confirm=yes``; refuses tenants with users unless
    ``force=true``. Audit history is retained.
    """
    from app.services.tenants import TenantNotEmptyError
    from app.services.tenants import decommission_tenant as decommission

    if confirm != "yes":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CONFIRM_REQUIRED",
                "message": "Pass confirm=yes to decommission — this is destructive",
            },
        )
    if not _valid_uuid(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TENANT", "message": "Not a valid tenant id"},
        )

    try:
        deleted = await decommission(
            tenant_id=tenant_id, actor_user_id=str(user["sub"]), force=force
        )
    except TenantNotEmptyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "TENANT_NOT_EMPTY", "message": str(e)},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TENANT_NOT_FOUND", "message": "No such tenant"},
        )
    return {"status": "deleted", "tenant_id": tenant_id}


@router.get("/admins", response_model=list[SuperadminOut])
async def list_superadmins(user: dict = Depends(require_platform_admin)):
    """Active platform superusers first, then revoked grants (history)."""
    from app.services.platform_admins import list_superadmins as list_all

    try:
        return [SuperadminOut(**row) for row in await list_all()]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None


@router.post("/admins", response_model=SuperadminOut, status_code=status.HTTP_201_CREATED)
async def grant_superadmin(
    request: AdminGrantRequest,
    user: dict = Depends(require_platform_admin),
):
    """Grant platform-superuser by user id or email (id wins when both)."""
    from app.services.platform_admins import grant_superadmin as grant

    target = request.user_id
    if not target and request.email:
        conn = await asyncpg.connect(_admin_dsn())
        try:
            target = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1 ORDER BY created_at LIMIT 1",
                request.email.strip().lower(),
            )
        finally:
            await conn.close()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "No such user"},
        )

    try:
        row = await grant(user_id=target, granted_by=str(user["sub"]))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None
    return SuperadminOut(
        user_id=row["user_id"],
        email=request.email,
        granted_by=row["granted_by"],
        granted_at=row["granted_at"],
        revoked_at=None,
        active=True,
    )


@router.delete("/admins/{user_id}")
async def revoke_superadmin(
    user_id: str,
    user: dict = Depends(require_platform_admin),
):
    """Revoke a platform-superuser grant (binds within ~60s via the cache)."""
    from app.services.platform_admins import revoke_superadmin as revoke

    if not _valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_USER", "message": "Not a valid user id"},
        )
    try:
        revoked = await revoke(user_id=user_id, revoked_by=str(user["sub"]))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"Control plane unavailable: {type(e).__name__}",
            },
        ) from None
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "GRANT_NOT_FOUND", "message": "No active grant for this user"},
        )
    return {"status": "revoked", "user_id": user_id}


@router.get("/audit", response_model=list[AdminAuditOut])
async def list_admin_audit(
    user: dict = Depends(require_platform_admin),
    limit: int = Query(default=50, ge=1, le=200),
):
    """The admin-action feed, newest first."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        rows = await conn.fetch(
            "SELECT actor_user_id, action, target_type, target_id, detail, created_at FROM admin_audit ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    finally:
        await conn.close()

    out = []
    for row in rows:
        detail = row["detail"]
        if isinstance(detail, str):
            detail = json.loads(detail)
        out.append(
            AdminAuditOut(
                actor_user_id=str(row["actor_user_id"]),
                action=row["action"],
                target_type=row["target_type"],
                target_id=row["target_id"],
                detail=detail,
                created_at=row["created_at"].isoformat(),
            )
        )
    return out
