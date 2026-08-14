"""Authentication endpoints — user login."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.security import verify_password
from app.db.session import get_auth_db

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


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest, db: AsyncSession = Depends(get_auth_db)
) -> LoginResponse:
    """Authenticate a user by email + password and mint a JWT access token."""
    email = request.email.strip().lower()

    try:
        tenant_uuid = uuid.UUID(request.tenant_id) if request.tenant_id else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        ) from None

    rows = (
        await db.execute(
            text(
                "SELECT id, tenant_id, email, hashed_password, roles "
                "FROM users "
                "WHERE email = :email AND (:tenant_id IS NULL OR tenant_id = :tenant_id::uuid) "
                "LIMIT 2"
            ),
            {"email": email, "tenant_id": tenant_uuid},
        )
    ).all()

    if len(rows) != 1 or not verify_password(request.password, rows[0].hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    user = rows[0]
    roles = list(user.roles or ["user"])
    token = create_access_token(user_id=str(user.id), tenant_id=str(user.tenant_id), roles=roles)

    return LoginResponse(
        access_token=token,
        user=UserOut(
            id=str(user.id),
            email=user.email,
            name=user.email.split("@")[0],
            tenant_id=str(user.tenant_id),
            roles=roles,
        ),
    )
