"""Tenant user management endpoints (Phase 23, ADR 009 §6).

Guard: ``require_tenant_admin`` — the tenant ``admin`` role or an active
platform superuser. Superusers may pass ``?tenant_id=`` to administer
another tenant (the admin portal uses this); tenant admins always operate
on their own tenant.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import require_tenant_admin

router = APIRouter()


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(default_factory=lambda: ["user"])


class UserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    roles: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    roles: list[str]
    status: str
    created_at: str | None = None
    last_login_at: str | None = None


class UserListResponse(BaseModel):
    users: list[UserOut]
    count: int


def _resolve_tenant(user: dict, requested: str | None) -> str:
    """Tenant scope: the caller's own, or any tenant for superusers."""
    if requested and requested != user["tenant_id"]:
        if not user.get("platform_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "NOT_TENANT_ADMIN",
                    "message": "Only platform administrators may manage other tenants",
                },
            )
        try:
            return str(uuid.UUID(requested))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TENANT", "message": "Not a valid tenant id"},
            ) from None
    return str(user["tenant_id"])


@router.get("", response_model=UserListResponse)
async def list_users(
    user: dict = Depends(require_tenant_admin),
    tenant_id: str | None = Query(default=None, description="Superuser: another tenant"),
):
    """The tenant's users (id, email, roles, status, last_login_at)."""
    from app.services.users import list_users as list_all

    # Resolve scope first so its 400/403s are never swallowed by the
    # catch-all below.
    scope = _resolve_tenant(user, tenant_id)
    try:
        rows = await list_all(scope)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"User store unavailable: {type(e).__name__}",
            },
        ) from None
    return UserListResponse(users=[UserOut(**r) for r in rows], count=len(rows))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    user: dict = Depends(require_tenant_admin),
):
    """Create a user in the caller's tenant (roles ⊆ user, admin)."""
    from app.services.users import InvalidRolesError, UserExistsError
    from app.services.users import create_user as create

    try:
        created = await create(
            tenant_id=str(user["tenant_id"]),
            email=request.email,
            password=request.password,
            roles=request.roles,
            actor_user_id=str(user["sub"]),
        )
    except InvalidRolesError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ROLES", "message": str(e)},
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
                "message": f"User store unavailable: {type(e).__name__}",
            },
        ) from None
    return UserOut(**created)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    user: dict = Depends(require_tenant_admin),
    tenant_id: str | None = Query(default=None, description="Superuser: another tenant"),
):
    """Update email / roles / status (enable-disable)."""
    from app.services.users import (
        InvalidRolesError,
        LastTenantAdminError,
        UserExistsError,
        UserNotFoundError,
    )
    from app.services.users import (
        update_user as update,
    )

    if not _valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_USER", "message": "Not a valid user id"},
        )

    scope = _resolve_tenant(user, tenant_id)
    try:
        updated = await update(
            tenant_id=scope,
            user_id=user_id,
            actor_user_id=str(user["sub"]),
            email=request.email,
            roles=request.roles,
            status=request.status,
        )
    except InvalidRolesError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ROLES", "message": str(e)},
        ) from None
    except UserExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "USER_EXISTS", "message": str(e)},
        ) from None
    except LastTenantAdminError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "LAST_TENANT_ADMIN", "message": str(e)},
        ) from None
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": str(e)},
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATUS", "message": str(e)},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"User store unavailable: {type(e).__name__}",
            },
        ) from None

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "No such user in this tenant"},
        )
    return UserOut(**updated)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    user: dict = Depends(require_tenant_admin),
    tenant_id: str | None = Query(default=None, description="Superuser: another tenant"),
):
    """Hard delete. Refuses the tenant's last active admin."""
    from app.services.users import LastTenantAdminError
    from app.services.users import delete_user as delete

    if not _valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_USER", "message": "Not a valid user id"},
        )

    scope = _resolve_tenant(user, tenant_id)
    try:
        deleted = await delete(
            tenant_id=scope,
            user_id=user_id,
            actor_user_id=str(user["sub"]),
        )
    except LastTenantAdminError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "LAST_TENANT_ADMIN", "message": str(e)},
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"User store unavailable: {type(e).__name__}",
            },
        ) from None

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "No such user in this tenant"},
        )
    return {"status": "deleted", "user_id": user_id}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    request: ResetPasswordRequest,
    user: dict = Depends(require_tenant_admin),
    tenant_id: str | None = Query(default=None, description="Superuser: another tenant"),
):
    """Admin sets a new password for a tenant user."""
    from app.services.users import reset_password as reset

    if not _valid_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_USER", "message": "Not a valid user id"},
        )

    scope = _resolve_tenant(user, tenant_id)
    try:
        ok = await reset(
            tenant_id=scope,
            user_id=user_id,
            new_password=request.password,
            actor_user_id=str(user["sub"]),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "CONTROL_PLANE_UNAVAILABLE",
                "message": f"User store unavailable: {type(e).__name__}",
            },
        ) from None

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "No such user in this tenant"},
        )
    return {"status": "reset", "user_id": user_id}


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
