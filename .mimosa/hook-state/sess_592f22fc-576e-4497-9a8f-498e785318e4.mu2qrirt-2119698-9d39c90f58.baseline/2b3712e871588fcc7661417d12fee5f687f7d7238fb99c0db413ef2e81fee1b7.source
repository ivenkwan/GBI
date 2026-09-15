"""Shared admin-DB helpers for scripts that run as the owner role.

seed_test_data.py and embed_schema.py do DDL/DML that the RLS-bound runtime
role (genbi_app) must never perform, and FORCE ROW LEVEL SECURITY binds even
the table owner — so admin scripts connect as the owner (DATABASE_URL_SYNC)
AND set the tenant GUC before touching tenant-scoped rows.
"""

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings


def owner_dsn(connection_url: str | None = None) -> str:
    """Owner DSN for asyncpg (postgresql://user:pass@host:port/db).

    Defaults to settings.DATABASE_URL_SYNC (owner credentials).
    """
    url = make_url(connection_url or settings.DATABASE_URL_SYNC)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def owner_connect(connection_url: str | None = None) -> asyncpg.Connection:
    """Connection as the owner role (DDL + admin DML)."""
    return await asyncpg.connect(owner_dsn(connection_url))


async def set_tenant_guc(conn: asyncpg.Connection, tenant_id: str) -> None:
    """Set the session-level tenant GUC.

    Required for INSERT/SELECT on RLS-FORCED tables even as the owner. Session
    scope (is_local=false) is intentional: admin scripts drive one connection
    per tenant pass.
    """
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
