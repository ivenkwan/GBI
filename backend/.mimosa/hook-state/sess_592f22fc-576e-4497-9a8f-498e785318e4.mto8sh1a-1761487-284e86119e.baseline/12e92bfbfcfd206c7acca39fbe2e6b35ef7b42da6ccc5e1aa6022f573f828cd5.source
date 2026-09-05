"""Database session and engine management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Control-plane engine: genbi_admin role (ADR 009) — the login endpoint
# (reads users across tenants + platform_admins + tenants.status) and the
# admin-plane services. It can read no business data.
admin_engine = create_async_engine(
    settings.database_url_admin,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)

admin_session = async_sessionmaker(
    admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yield an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_admin_db() -> AsyncSession:
    """FastAPI dependency: session on the control-plane genbi_admin role."""
    async with admin_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
