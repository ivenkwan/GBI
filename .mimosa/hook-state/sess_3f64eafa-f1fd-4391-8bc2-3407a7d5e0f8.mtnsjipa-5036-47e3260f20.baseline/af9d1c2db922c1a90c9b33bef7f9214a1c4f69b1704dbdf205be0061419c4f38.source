"""Generic single-database configuration (async engine).

See: https://alembic.sqlalchemy.org/en/latest/
The app ships only asyncpg (no psycopg2), so the sync URL is normalized to
the asyncpg driver and migrations run through an AsyncEngine with run_sync.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.models import Base

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from settings — normalize to the asyncpg driver.
# NOTE: str(URL) masks the password as "***"; render explicitly.
url = make_url(settings.DATABASE_URL_SYNC)
if url.drivername in ("postgresql", "postgresql+psycopg2"):
    url = url.set(drivername="postgresql+asyncpg")
config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode via an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
