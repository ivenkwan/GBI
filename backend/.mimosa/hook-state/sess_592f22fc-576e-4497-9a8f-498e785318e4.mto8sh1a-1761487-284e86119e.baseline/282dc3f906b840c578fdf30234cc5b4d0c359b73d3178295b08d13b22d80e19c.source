"""Per-tenant user management (Phase 23, ADR 009 §6).

Runs on the control-plane ``genbi_admin`` role with the tenant GUC set —
belt-and-suspenders over the permissive control-plane policy: every
statement also carries an explicit ``tenant_id`` predicate, so tightening
the policy later changes nothing here.

Rules enforced here, not just in the API:
- roles ⊆ {user, admin} (validated before any write);
- email unique per tenant (composite unique constraint, 0008+0010);
- the tenant's last ACTIVE admin cannot be deleted, demoted, or disabled
  (a tenant must always be administrable);
- every mutation writes an ``admin_audit`` row (fail-open).

Password changes go through bcrypt (`app.core.security`); no credential
material is ever logged. Login stamps ``last_login_at`` (that write lives
in the login endpoint).
"""

import json
import uuid

import asyncpg

from app.core.auth import _admin_dsn
from app.core.cache import get_cache
from app.core.security import hash_password, verify_password
from app.services.admin_audit import record_admin_action

ALLOWED_ROLES = frozenset({"user", "admin"})


class UserExistsError(Exception):
    """The email already exists in this tenant."""


class UserNotFoundError(Exception):
    """No such user in this tenant."""


class LastTenantAdminError(Exception):
    """The operation would leave the tenant without an active admin."""


class InvalidRolesError(Exception):
    """Roles outside {user, admin}."""


async def _connect(tenant_id: str) -> asyncpg.Connection:
    """Control-plane connection with the tenant GUC set (defense in depth)."""
    conn = await asyncpg.connect(_admin_dsn())
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
    return conn


def _validate_roles(roles: list[str]) -> None:
    if not roles or not set(roles) <= ALLOWED_ROLES:
        raise InvalidRolesError(f"roles must be a non-empty subset of {sorted(ALLOWED_ROLES)}")


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def list_users(tenant_id: str) -> list[dict]:
    """The tenant's users. Raises on DB failure."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT id, email, roles, status, created_at, last_login_at FROM users WHERE tenant_id = $1::uuid ORDER BY created_at",
            tenant_id,
        )
    finally:
        await conn.close()
    return _map(rows)


async def get_user(tenant_id: str, user_id: str) -> dict | None:
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, roles, status, created_at, last_login_at FROM users WHERE tenant_id = $1::uuid AND id = $2::uuid",
            tenant_id,
            user_id,
        )
    finally:
        await conn.close()
    if row is None:
        return None
    return _map([row])[0]


def _map(rows) -> list[dict]:
    out = []
    for row in rows:
        roles = row["roles"]
        if isinstance(roles, str):
            roles = json.loads(roles)
        out.append(
            {
                "id": str(row["id"]),
                "email": row["email"],
                "roles": list(roles or ["user"]),
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
                "last_login_at": row["last_login_at"].isoformat() if row["last_login_at"] else None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


async def create_user(
    tenant_id: str, email: str, password: str, roles: list[str], actor_user_id: str
) -> dict:
    """Create a user in the tenant. Raises UserExistsError / InvalidRolesError."""
    _validate_roles(roles)
    normalized = email.strip().lower()
    user_id = str(uuid.uuid4())

    conn = await _connect(tenant_id)
    try:
        try:
            await conn.execute(
                "INSERT INTO users (id, tenant_id, email, hashed_password, roles, status) VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, 'active')",
                user_id,
                tenant_id,
                normalized,
                hash_password(password),
                json.dumps(roles),
            )
        except asyncpg.UniqueViolationError as e:
            raise UserExistsError(f"user already exists in this tenant: {normalized}") from e
    finally:
        await conn.close()

    await record_admin_action(
        actor_user_id=actor_user_id,
        action="user.create",
        target_type="user",
        target_id=user_id,
        detail={"tenant_id": tenant_id, "email": normalized, "roles": roles},
    )
    return {"id": user_id, "email": normalized, "roles": roles, "status": "active"}


async def _active_admin_count(conn, tenant_id: str, exclude_user_id: str) -> int:
    """Active admins in the tenant other than the excluded user."""
    return (
        await conn.fetchval(
            "SELECT count(*) FROM users WHERE tenant_id = $1::uuid AND id != $2::uuid AND status = 'active' AND roles @> '\"admin\"'::jsonb",
            tenant_id,
            exclude_user_id,
        )
        or 0
    )


async def update_user(
    tenant_id: str,
    user_id: str,
    actor_user_id: str,
    email: str | None = None,
    roles: list[str] | None = None,
    status: str | None = None,
) -> dict | None:
    """Update email / roles / status. None when the user does not exist.

    The last active admin cannot be demoted or disabled
    (LastTenantAdminError). Field-specific static statements, one
    transaction.
    """
    if roles is not None:
        _validate_roles(roles)
    if status is not None and status not in ("active", "disabled"):
        raise ValueError("status must be active|disabled")

    conn = await _connect(tenant_id)
    try:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT id, email, roles, status FROM users WHERE tenant_id = $1::uuid AND id = $2::uuid",
                tenant_id,
                user_id,
            )
            if existing is None:
                return None

            current_roles = existing["roles"]
            if isinstance(current_roles, str):
                current_roles = json.loads(current_roles)
            current_roles = list(current_roles or ["user"])

            # Last-active-admin guard: demote (roles loses admin) or disable
            is_admin_now = "admin" in current_roles and existing["status"] == "active"
            loses_admin = roles is not None and "admin" not in roles
            gets_disabled = status == "disabled"
            if is_admin_now and (loses_admin or gets_disabled):
                others = await _active_admin_count(conn, tenant_id, user_id)
                if others == 0:
                    raise LastTenantAdminError(
                        "cannot demote or disable the tenant's last active admin"
                    )

            if email is not None and email.strip().lower() != existing["email"]:
                try:
                    await conn.execute(
                        "UPDATE users SET email = $3, updated_at = NOW() WHERE tenant_id = $1::uuid AND id = $2::uuid",
                        tenant_id,
                        user_id,
                        email.strip().lower(),
                    )
                except asyncpg.UniqueViolationError as e:
                    raise UserExistsError(f"user already exists in this tenant: {email}") from e
            if roles is not None:
                await conn.execute(
                    "UPDATE users SET roles = $3::jsonb, updated_at = NOW() WHERE tenant_id = $1::uuid AND id = $2::uuid",
                    tenant_id,
                    user_id,
                    json.dumps(roles),
                )
            if status is not None:
                await conn.execute(
                    "UPDATE users SET status = $3, updated_at = NOW() WHERE tenant_id = $1::uuid AND id = $2::uuid",
                    tenant_id,
                    user_id,
                    status,
                )
            final = await conn.fetchrow(
                "SELECT id, email, roles, status, created_at, last_login_at FROM users WHERE tenant_id = $1::uuid AND id = $2::uuid",
                tenant_id,
                user_id,
            )
    finally:
        await conn.close()

    await record_admin_action(
        actor_user_id=actor_user_id,
        action="user.update",
        target_type="user",
        target_id=user_id,
        detail={"tenant_id": tenant_id, "email": email, "roles": roles, "status": status},
    )
    return _map([final])[0]


async def reset_password(
    tenant_id: str, user_id: str, new_password: str, actor_user_id: str
) -> bool:
    """Admin sets a new password. False when the user does not exist."""
    conn = await _connect(tenant_id)
    try:
        updated = await conn.execute(
            "UPDATE users SET hashed_password = $3, updated_at = NOW() WHERE tenant_id = $1::uuid AND id = $2::uuid",
            tenant_id,
            user_id,
            hash_password(new_password),
        )
    finally:
        await conn.close()

    if updated != "UPDATE 1":
        return False
    await record_admin_action(
        actor_user_id=actor_user_id,
        action="user.reset_password",
        target_type="user",
        target_id=user_id,
        detail={"tenant_id": tenant_id},
    )
    return True


async def delete_user(tenant_id: str, user_id: str, actor_user_id: str) -> bool:
    """Hard delete. Refuses the last active admin. False when not found.

    Owned conversations/reports/dashboards stay (tenant assets); audit
    history stays (no FK by design).
    """
    conn = await _connect(tenant_id)
    try:
        existing = await conn.fetchrow(
            "SELECT id, roles, status FROM users WHERE tenant_id = $1::uuid AND id = $2::uuid",
            tenant_id,
            user_id,
        )
        if existing is None:
            return False

        roles = existing["roles"]
        if isinstance(roles, str):
            roles = json.loads(roles)
        if "admin" in (roles or []) and existing["status"] == "active":
            others = await _active_admin_count(conn, tenant_id, user_id)
            if others == 0:
                raise LastTenantAdminError("cannot delete the tenant's last active admin")

        deleted = await conn.execute(
            "DELETE FROM users WHERE tenant_id = $1::uuid AND id = $2::uuid",
            tenant_id,
            user_id,
        )
    finally:
        await conn.close()

    await record_admin_action(
        actor_user_id=actor_user_id,
        action="user.delete",
        target_type="user",
        target_id=user_id,
        detail={"tenant_id": tenant_id},
    )
    return deleted == "DELETE 1"


async def change_password(
    tenant_id: str, user_id: str, current_password: str, new_password: str
) -> bool:
    """Self-service password change. False when the current password is wrong.

    A wrong current password registers a login-throttle failure for the
    user's email (the same counter login uses), so brute-forcing the
    current password locks the account out.
    """
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT email, hashed_password FROM users WHERE tenant_id = $1::uuid AND id = $2::uuid",
            tenant_id,
            user_id,
        )
        if row is None:
            return False
        if not verify_password(current_password, row["hashed_password"]):
            await get_cache().register_failed_login(row["email"])
            return False
        await conn.execute(
            "UPDATE users SET hashed_password = $3, updated_at = NOW() WHERE tenant_id = $1::uuid AND id = $2::uuid",
            tenant_id,
            user_id,
            hash_password(new_password),
        )
    finally:
        await conn.close()
    # Self-service changes are not admin actions — no admin_audit entry, but
    # the login-throttle counter reset happens on the next successful login.
    return True
