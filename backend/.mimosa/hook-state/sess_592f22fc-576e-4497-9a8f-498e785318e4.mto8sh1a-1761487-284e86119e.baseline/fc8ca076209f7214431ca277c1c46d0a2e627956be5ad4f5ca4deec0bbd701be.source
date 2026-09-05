"""
PostgreSQL connector implementation — asyncpg-backed, read-only enforced.

This connector implements BaseConnector for PostgreSQL with:

- Read-only transaction enforcement (SET TRANSACTION READ ONLY)
- 30-second statement_timeout injection
- Parameterized query support via asyncpg
- Schema metadata retrieval (tables, columns, types, descriptions)
- Connection pooling via SQLAlchemy async engine
- Destructive SQL blocking at the driver level

Usage:
    connector = PostgreSQLConnector(connection_url="postgresql+asyncpg://...")
    await connector.connect()
    results = await connector.execute("SELECT region, SUM(revenue) FROM sales GROUP BY region")
    schema = await connector.get_schema()
    await connector.disconnect()
"""

from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql.elements import TextClause

from app.connectors.base import BaseConnector
from app.core.logging import logger


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL database connector with read-only enforcement.

    All queries go through a connection that sets:
    - SET TRANSACTION READ ONLY (prevents any write at DB level)
    - SET statement_timeout = '30s' (caps query execution time)
    - SET application_name = 'genbi' (identifies queries in pg_stat_activity)

    The connector uses a separate async engine instance per data source
    so it can connect to the tenant's actual data warehouse, not just
    the metadata database.
    """

    name = "postgresql"
    _read_only = True

    def __init__(
        self,
        connection_url: str,
        schema: str = "public",
        tenant_id: str | None = None,
        pool_size: int = 10,
        max_overflow: int = 5,
        echo: bool = False,
    ):
        """Initialize the connector.

        Args:
            connection_url: SQLAlchemy asyncpg connection string.
            schema: Default schema for query resolution.
            tenant_id: Tenant identifier. When set, the per-transaction GUC
                ``app.current_tenant_id`` is injected so PostgreSQL row-level
                security policies (see infra/postgres/init.sql) scope every
                query to this tenant. Required for multi-tenant queries.
            pool_size: Connection pool size.
            max_overflow: Max overflow connections.
            echo: SQL echo mode for debugging.
        """
        self.connection_url = connection_url
        self.schema = schema
        self.tenant_id = tenant_id
        self._engine = None
        self._session_factory = None
        self._connected = False
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._echo = echo

    async def connect(self) -> None:
        """Establish connection pool."""
        if self._connected:
            return

        logger.info(
            "Connecting to PostgreSQL",
            schema=self.schema,
            pool_size=self._pool_size,
        )

        self._engine = create_async_engine(
            self.connection_url,
            echo=self._echo,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "server_settings": {
                    "application_name": "genbi",
                },
            },
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Test the connection
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

        self._connected = True
        logger.info("PostgreSQL connected successfully")

    async def execute(
        self,
        sql: str | TextClause | Select,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """Execute a read-only SQL query and return results as dicts.

        Args:
            sql: SQL query string (parameterized with :param placeholders) or
                a SQLAlchemy statement construct built from ``select()``.
            params: Query parameters for parameterized queries.

        Returns:
            List of dicts, one per row.

        Raises:
            ConnectionError: If not connected.
            ValueError: If the SQL is not a SELECT or contains destructive patterns.
        """
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        # Sanity check — must be SELECT. Statement constructs are compiled
        # from select() internally, so they are read-only by construction.
        if isinstance(sql, str):
            sql_stripped = sql.strip().upper()
            if not sql_stripped.startswith(("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE")):
                raise ValueError(
                    f"Only SELECT/WITH/EXPLAIN queries are allowed through this connector. "
                    f"Received: {sql[:100]}"
                )

        # Read-only enforcement + timeout — each SET must be its own execute()
        # because the asyncpg extended (prepared-statement) protocol does not
        # allow multiple semicolon-separated statements in a single round-trip.
        # Issuing them separately keeps the connector the single source of these
        # guarantees for every code path that hits the database.
        async with self._session_factory() as session:
            # Mark the transaction read-only at the DB level. Must precede any
            # data statement; emitted first so the transaction begins read-only.
            await session.execute(text("SET TRANSACTION READ ONLY"))
            await session.execute(text("SET LOCAL statement_timeout = '30s'"))
            await session.execute(text("SET LOCAL default_transaction_read_only = on"))
            # Tenant GUC — drives row-level security policies (see init.sql).
            # Parameterized via the GUC string only when a tenant is bound, so
            # RLS scopes every SELECT to this tenant.
            if self.tenant_id:
                await session.execute(
                    text("SET LOCAL app.current_tenant_id = :tid"),
                    {"tid": str(self.tenant_id)},
                )

            result = await session.execute(
                text(sql) if isinstance(sql, str) else sql,
                params or {},
            )

            # Convert rows to dicts
            if result.returns_rows:
                columns = list(result.keys())
                rows = []
                for row in result.fetchall():
                    row_dict = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        # Convert non-serializable types
                        if hasattr(val, "isoformat"):
                            val = val.isoformat()
                        row_dict[col] = val
                    rows.append(row_dict)
                return rows

            return []

    async def execute_raw(self, sql: str) -> Any:
        """Execute SQL and return raw cursor result.

        For EXPLAIN plans, introspection queries, and other non-data queries.
        Applies the same timeout + read-only enforcement as ``execute``.
        """
        if not self._connected:
            raise ConnectionError("Not connected. Call connect() first.")

        async with self._session_factory() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            await session.execute(text("SET LOCAL statement_timeout = '30s'"))
            if self.tenant_id:
                await session.execute(
                    text("SET LOCAL app.current_tenant_id = :tid"),
                    {"tid": str(self.tenant_id)},
                )
            result = await session.execute(text(sql))
            return result

    async def explain(self, sql: str) -> dict:
        """Get EXPLAIN plan for a SQL query.

        Returns:
            Dict with plan_type, plan_text, estimated_cost, and estimated_rows.
        """
        try:
            result = await self.execute_raw(f"EXPLAIN (FORMAT JSON) {sql}")
            plan = result.scalar_one()
            import json

            plan_data = json.loads(plan) if isinstance(plan, str) else plan

            first_plan = (
                plan_data[0]["Plan"] if isinstance(plan_data, list) else plan_data.get("Plan", {})
            )
            return {
                "plan_type": "EXPLAIN (FORMAT JSON)",
                "plan_text": json.dumps(plan_data, indent=2),
                "estimated_cost": first_plan.get("Total Cost", 0),
                "estimated_rows": first_plan.get("Plan Rows", 0),
            }
        except Exception as e:
            logger.warning(f"EXPLAIN failed: {e}")
            return {
                "plan_type": "EXPLAIN",
                "plan_text": f"EXPLAIN failed: {e}",
                "estimated_cost": 0,
                "estimated_rows": 0,
            }

    async def get_schema(self) -> dict:
        """Retrieve table and column metadata for the configured schema.

        Returns:
            Dict with tables list, each containing name, columns, row_count, and description.
        """
        if not self._connected:
            await self.connect()

        query = """
            SELECT
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                pg_catalog.obj_description(
                    (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass,
                    'pg_class'
                ) AS table_description,
                pg_catalog.col_description(
                    (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass,
                    c.ordinal_position
                ) AS column_description
            FROM information_schema.tables t
            JOIN information_schema.columns c
                ON t.table_schema = c.table_schema
                AND t.table_name = c.table_name
            WHERE t.table_schema = :schema
                AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name, c.ordinal_position
        """

        rows = await self.execute(query, {"schema": self.schema})

        # Group by table
        tables: dict[str, dict] = {}
        for row in rows:
            table_name = row["table_name"]
            if table_name not in tables:
                tables[table_name] = {
                    "table_name": table_name,
                    "schema": self.schema,
                    "description": row.get("table_description") or "",
                    "columns": [],
                }
            tables[table_name]["columns"].append(
                {
                    "column_name": row["column_name"],
                    "data_type": row["data_type"],
                    "is_nullable": row["is_nullable"] == "YES",
                    "description": row.get("column_description") or "",
                }
            )

        # Get approximate row counts
        for table_name in tables:
            try:
                count_result = await self.execute(
                    f"SELECT COUNT(*) AS cnt FROM {self.schema}.{table_name}"
                )
                tables[table_name]["row_count"] = count_result[0]["cnt"] if count_result else 0
            except Exception:
                tables[table_name]["row_count"] = -1  # unknown

        return {
            "schema": self.schema,
            "tables": list(tables.values()),
            "table_count": len(tables),
        }

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._connected = False
            logger.info("PostgreSQL disconnected")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
