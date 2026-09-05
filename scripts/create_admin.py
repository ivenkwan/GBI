"""Bootstrap / manage platform superusers (Phase 21, ADR 009 §5).

Runs as the owner role (DATABASE_URL_SYNC). Idempotent: grants the
platform-admin role to an existing user by email, optionally creating the
user (and its tenant) first. The password is read from the environment
(GENBI_SUPERUSER_PASSWORD) or a hidden prompt — never an argument default
and never echoed.

Usage (host or `make admin-create` inside the backend container):
    PYTHONPATH=/app uv run python scripts/create_admin.py --email you@corp.example
    # with an initial user + tenant:
    ... --email you@corp.example --new-tenant-name "Acme Corp" --new-tenant-slug acme
"""

import argparse
import asyncio
import getpass
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.logging import logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402


def owner_dsn() -> str:
    from sqlalchemy.engine import make_url

    url = make_url(settings.DATABASE_URL_SYNC)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Grant platform-superuser to a user")
    parser.add_argument("--email", required=True, help="user email (case-insensitive)")
    parser.add_argument("--new-tenant-name", help="create the user's tenant first (with the user)")
    parser.add_argument(
        "--new-tenant-slug", help="slug for the new tenant (required with --new-tenant-name)"
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = os.environ.get("GENBI_SUPERUSER_PASSWORD") or getpass.getpass(
        f"Password for {email} (input hidden, only used when creating the user): "
    )

    conn = await asyncpg.connect(owner_dsn())
    try:
        user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1 LIMIT 1", email)

        if user_id is None:
            if not (args.new_tenant_name and args.new_tenant_slug):
                logger.error(
                    "No user with email %s — pass --new-tenant-name/--new-tenant-slug "
                    "to create the user (and its tenant) first",
                    email,
                )
                return 2
            tenant_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO tenants (id, name, slug, status) VALUES ($1::uuid, $2, $3, 'active')",
                    tenant_id,
                    args.new_tenant_name,
                    args.new_tenant_slug,
                )
                await conn.execute(
                    "INSERT INTO users (id, tenant_id, email, hashed_password, roles) VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb)",
                    user_id,
                    tenant_id,
                    email,
                    hash_password(password),
                    '["admin","user"]',
                )
            logger.info("Created user %s in new tenant %s", email, args.new_tenant_slug)

        await conn.execute(
            "INSERT INTO platform_admins (user_id) VALUES ($1::uuid) ON CONFLICT (user_id) DO UPDATE SET granted_at = NOW(), revoked_by = NULL, revoked_at = NULL",
            user_id,
        )
        await conn.execute(
            "INSERT INTO admin_audit (actor_user_id, action, target_type, target_id, detail) VALUES ($1::uuid, 'platform_admin.bootstrap', 'user', $2::uuid, NULL)",
            user_id,
            user_id,
        )
        logger.info("Granted platform-superuser to %s (user %s)", email, user_id)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
