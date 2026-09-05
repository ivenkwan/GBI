"""Authentication and authorization — JWT + RBAC + control-plane guards.

Two scopes of authority (ADR 009 §1):
- tenant roles ride the JWT ``roles`` claim (tenant-scoped capabilities);
- platform superusers carry a ``platform_admin`` claim minted at login from
  the ``platform_admins`` grant table, and ``require_platform_admin``
  re-verifies the grant behind a 60-second cache — revocation binds within
  a minute, not at token expiry.

Tenant suspension is enforced the same way: ``get_current_user`` checks a
60-second-cached ``tenants.status`` for the token's tenant and rejects with
403 TENANT_SUSPENDED. Both checks fail OPEN (DB/cache outage must not lock
every endpoint); suspension is a control, not a security boundary.
"""

from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.engine import make_url

from app.core.config import settings

security = HTTPBearer()


def create_access_token(
    user_id: str,
    tenant_id: str,
    roles: list[str] | None = None,
    expires_minutes: int | None = None,
    platform_admin: bool = False,
) -> str:
    """Create a JWT access token."""
    expires_delta = timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    expire = datetime.now(UTC) + expires_delta

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or ["user"],
        "platform_admin": platform_admin,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def _admin_dsn() -> str:
    """asyncpg DSN for the control-plane role (plain driver)."""
    url = make_url(settings.database_url_admin)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _lookup_tenant_status(tenant_id: str) -> str | None:
    """Tenants.status via the control-plane role. None when unknown."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        return await conn.fetchval("SELECT status FROM tenants WHERE id = $1::uuid", tenant_id)
    finally:
        await conn.close()


async def _lookup_platform_admin(user_id: str) -> bool:
    """True when the user has an active (unrevoked) platform-admin grant."""
    conn = await asyncpg.connect(_admin_dsn())
    try:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM platform_admins WHERE user_id = $1::uuid AND revoked_at IS NULL) AS active",
            user_id,
        )
    finally:
        await conn.close()


async def _tenant_is_suspended(tenant_id: str) -> bool:
    """Cached suspension check. Fail-open on any problem (unknown = allowed)."""
    from app.core.cache import get_cache

    try:
        cached = await get_cache().get_tenant_status(tenant_id)
        current = cached if cached is not None else await _lookup_tenant_status(tenant_id)
        if cached is None and current is not None:
            await get_cache().set_tenant_status(tenant_id, current)
        return current == "suspended"
    except Exception:
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency: extract and validate the current user from JWT.

    Also rejects suspended tenants (60s-cached status, fail-open).
    """
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": "Token missing subject claim"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token is expired or invalid"},
        ) from None

    tenant_id = payload.get("tenant_id")
    if tenant_id and await _tenant_is_suspended(str(tenant_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_SUSPENDED",
                "message": "This tenant is suspended — contact the platform administrator",
            },
        )
    return payload


async def require_platform_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    """Guard for /admin routes: JWT claim + cached grant-table re-check.

    The claim alone is not trusted beyond its 60-second window: a revoked
    superuser's unexpired token loses power at the next cache expiry. The
    grant lookup fails OPEN (an outage must not lock the admin plane) —
    the claim itself was minted at login from the same table.
    """
    if not user.get("platform_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_PLATFORM_ADMIN",
                "message": "Platform administrator privileges required",
            },
        )

    from app.core.cache import get_cache

    user_id = str(user["sub"])
    try:
        cached = await get_cache().get_platform_admin(user_id)
        active = cached if cached is not None else await _lookup_platform_admin(user_id)
        if cached is None:
            await get_cache().set_platform_admin(user_id, bool(active))
    except Exception:
        active = True  # fail-open: claim was minted from the grant table

    if not active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_PLATFORM_ADMIN",
                "message": "Platform administrator privileges required",
            },
        )
    return user
