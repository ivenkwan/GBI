"""Authentication endpoints — user login with failed-attempt throttling.

Since Phase 21 (ADR 009) login runs on the control-plane ``genbi_admin``
role (which superseded the retired ``genbi_auth``): the lookup joins
``tenants.status`` (suspended tenants cannot log in) and
``platform_admins`` (active grants mint the ``platform_admin`` JWT claim).
"""

import json
import uuid

import asyncpg
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import create_access_token
from app.core.cache import get_cache
from app.core.config import settings
from app.core.security import verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    # Optional: disambiguate when the same email exists in multiple tenants.
    tenant_id: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    tenant_id: str
    roles: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


async def _reject(request_email: str) -> HTTPException:
    """Record a failed attempt and return the standard 401."""
    await get_cache().register_failed_login(request_email)
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate a user by email + password and mint a JWT access token.

    Throttled: LOGIN_MAX_FAILURES failed attempts per email within
    LOGIN_LOCKOUT_SECONDS → 429. Indistinguishable 401s for every failure
    mode (no account enumeration). Suspended tenants get 403
    TENANT_SUSPENDED; an active platform_admin grant mints the
    platform_admin claim.
    """
    email = request.email.strip().lower()

    # Lockout check before any DB work (the genbi_auth lookup is a
    # cross-tenant read oracle — throttle brute force).
    cache = get_cache()
    if await cache.login_failures(email) >= settings.LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "TOO_MANY_ATTEMPTS",
                "message": "Too many failed attempts. Try again later.",
            },
        )

    try:
        tenant_uuid = uuid.UUID(request.tenant_id) if request.tenant_id else None
    except ValueError:
        raise await _reject(email) from None

    from app.core.auth import _admin_dsn

    conn = await asyncpg.connect(_admin_dsn())
    try:
        rows = await conn.fetch(
            "SELECT u.id, u.tenant_id, u.email, u.hashed_password, u.roles, t.status, EXISTS(SELECT 1 FROM platform_admins pa WHERE pa.user_id = u.id AND pa.revoked_at IS NULL) AS platform_admin FROM users u JOIN tenants t ON t.id = u.tenant_id WHERE u.email = $1 AND (CAST($2 AS uuid) IS NULL OR u.tenant_id = CAST($2 AS uuid)) LIMIT 2",
            email,
            tenant_uuid,
        )
    finally:
        await conn.close()

    if len(rows) != 1 or not verify_password(request.password, rows[0]["hashed_password"]):
        raise await _reject(email)

    user = rows[0]
    if user["status"] == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_SUSPENDED",
                "message": "This tenant is suspended — contact the platform administrator",
            },
        )

    # Raw asyncpg returns JSONB as text (SQLAlchemy used to parse it).
    roles_raw = user["roles"]
    if isinstance(roles_raw, str):
        roles_raw = json.loads(roles_raw)
    roles = list(roles_raw or ["user"])
    token = create_access_token(
        user_id=str(user["id"]),
        tenant_id=str(user["tenant_id"]),
        roles=roles,
        platform_admin=bool(user["platform_admin"]),
    )

    await cache.clear_failed_logins(email)

    return LoginResponse(
        access_token=token,
        user=UserOut(
            id=str(user["id"]),
            email=user["email"],
            name=user["email"].split("@")[0],
            tenant_id=str(user["tenant_id"]),
            roles=roles,
        ),
    )
