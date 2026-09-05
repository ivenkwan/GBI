"""Conftest — shared test fixtures and configuration."""

import os
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url


def role_dsn(username: str, password: str) -> str:
    """DSN for a DB role, preserving the host/database of DATABASE_URL.

    CI points DATABASE_URL at its service container (genbi_test DB); dev
    points at localhost — deriving keeps the tests correct in both.
    """
    from app.core.config import settings

    url = make_url(settings.DATABASE_URL).set(username=username, password=password)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def app_role_dsn() -> str:
    """DSN for the RLS-bound runtime role (created by Alembic 0002)."""
    return role_dsn(
        os.environ.get("GENBI_APP_DB_USER", "genbi_app"),
        os.environ.get("GENBI_APP_DB_PASSWORD", "genbi_app"),
    )


def auth_role_dsn() -> str:
    """DSN for the retired genbi_auth role (kept for its removal-verification
    tests; Phase 21 dropped the role's grants)."""
    return role_dsn(
        os.environ.get("GENBI_AUTH_DB_USER", "genbi_auth"),
        os.environ.get("GENBI_AUTH_DB_PASSWORD", "genbi_auth"),
    )


def admin_role_dsn() -> str:
    """DSN for the control-plane genbi_admin role (created by the 0008 RLS file)."""
    return role_dsn(
        os.environ.get("GENBI_ADMIN_DB_USER", "genbi_admin"),
        os.environ.get("GENBI_ADMIN_DB_PASSWORD", "genbi_admin"),
    )


def owner_dsn() -> str:
    """DSN for the owner role (DATABASE_URL_SYNC), asyncpg driver."""
    from app.core.config import settings

    url = make_url(settings.DATABASE_URL_SYNC)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def db_reachable(dsn: str) -> bool:
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def owner_conn() -> AsyncGenerator[asyncpg.Connection]:
    """Owner-role connection for test data setup/teardown."""
    conn = await asyncpg.connect(owner_dsn())
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
def tenant_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_sales_data() -> list[dict]:
    """Sample query result: sales by region."""
    return [
        {"region": "North", "total_revenue": 120000},
        {"region": "South", "total_revenue": 95000},
        {"region": "East", "total_revenue": 140000},
        {"region": "West", "total_revenue": 110000},
    ]


@pytest.fixture
def sample_time_series_data() -> list[dict]:
    """Sample query result: monthly revenue."""
    return [
        {"month": "2026-01", "revenue": 50000},
        {"month": "2026-02", "revenue": 55000},
        {"month": "2026-03", "revenue": 62000},
        {"month": "2026-04", "revenue": 58000},
    ]


# ---------------------------------------------------------------------------
# Agent fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_config():
    """Default AgentConfig for tests — uses mocked LLM, not real API."""
    from app.agents.base import AgentConfig

    return AgentConfig(
        model_name="claude-haiku-4",
        temperature=0,
        max_tokens=1024,
    )
