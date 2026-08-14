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

# Login-path engine: genbi_auth role — SELECT on `users` across tenants
# (users_login_lookup policy) and nothing else. See ADR 006.
auth_engine = create_async_engine(
    settings.database_url_auth,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)

auth_session = async_sessionmaker(
    auth_engine,
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


async def get_auth_db() -> AsyncSession:
    """FastAPI dependency: session on the login-only genbi_auth role."""
    async with auth_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
