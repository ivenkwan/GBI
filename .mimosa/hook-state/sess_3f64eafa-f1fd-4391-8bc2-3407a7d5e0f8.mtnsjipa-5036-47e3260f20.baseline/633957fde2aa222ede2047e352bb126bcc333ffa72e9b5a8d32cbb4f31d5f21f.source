"""Schema embedding pipeline — nightly sync of database schema to pgvector.

Generates embeddings for all table/column metadata and stores them in the
schema_embeddings table for semantic search by NL2SQLAgent.

Connects as the OWNER role (scripts/db_admin.owner_connect): schema_embeddings
is RLS-enrolled, so the tenant GUC is set on the connection before any write
(FORCE RLS binds the owner too).

Usage (from the repo root, backend venv active):
    PYTHONPATH=backend uv run python scripts/embed_schema.py                # full sync
    PYTHONPATH=backend uv run python scripts/embed_schema.py --domain sales  # single domain
    PYTHONPATH=backend uv run python scripts/embed_schema.py --dry-run       # preview without writing
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.logging import logger
from db_admin import owner_connect, set_tenant_guc

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def get_schema_metadata(conn, schema: str = "public") -> list[dict]:
    """Retrieve all table and column metadata from information_schema.

    Returns a list of dicts with table/column metadata grouped per table.
    """
    rows = await conn.fetch(
        """
        SELECT
            t.table_schema,
            t.table_name,
            c.column_name,
            c.data_type,
            c.udt_name,
            c.is_nullable,
            c.ordinal_position,
            pgd.description AS column_description,
            obj_description(pgc.oid) AS table_description
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON t.table_schema = c.table_schema
            AND t.table_name = c.table_name
        LEFT JOIN pg_catalog.pg_class pgc
            ON pgc.relname = t.table_name
            AND pgc.relnamespace = (
                SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = t.table_schema
            )
        LEFT JOIN pg_catalog.pg_description pgd
            ON pgd.objoid = pgc.oid
            AND pgd.objsubid = c.ordinal_position
        WHERE t.table_schema = $1
            AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position
        """,
        schema,
    )

    # Group columns by table
    tables: dict[str, dict] = {}
    for row in rows:
        record = dict(row)
        key = f"{record['table_schema']}.{record['table_name']}"
        if key not in tables:
            tables[key] = {
                "table_schema": record["table_schema"],
                "table_name": record["table_name"],
                "full_name": key,
                "table_description": record["table_description"] or "",
                "columns": [],
            }

        tables[key]["columns"].append({
            "column_name": record["column_name"],
            "data_type": record["data_type"],
            "udt_name": record["udt_name"],
            "is_nullable": record["is_nullable"],
            "ordinal_position": record["ordinal_position"],
            "description": record["column_description"] or "",
        })

    return list(tables.values())


def build_embedding_text(table: dict) -> str:
    """Build a text representation of a table for embedding.

    The embedding text is what gets vectorized — it should be rich with
    semantic meaning about the table and its columns.
    """
    parts = [f"Table: {table['full_name']}"]

    if table.get("table_description"):
        parts.append(f"Description: {table['table_description']}")

    parts.append("Columns:")
    for col in table["columns"]:
        col_text = f"  - {col['column_name']} ({col['data_type']}"
        if col["udt_name"] != col["data_type"]:
            col_text += f"/{col['udt_name']}"
        col_text += ")"
        if col.get("description"):
            col_text += f": {col['description']}"
        parts.append(col_text)

    return "\n".join(parts)


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for schema metadata text.

    Delegates to the shared provider (app.core.embeddings — OpenAI
    text-embedding-3-small; the original Anthropic embeddings call targeted
    a model that does not exist).
    """
    from app.core.embeddings import embed_text

    return await embed_text(text)


async def sync_schema(
    conn,
    schema: str = "public",
    dry_run: bool = False,
) -> dict[str, int]:
    """Sync schema metadata to the schema_embeddings table.

    For each table in information_schema:
        1. Build embedding text from table + column metadata
        2. Generate embedding via Anthropic API
        3. Upsert into schema_embeddings with tenant_id

    Returns:
        Dict with counts: tables_processed, embeddings_generated, errors.
    """
    tables = await get_schema_metadata(conn, schema)

    if not tables:
        logger.warning(f"No tables found in schema '{schema}'")
        return {"tables_processed": 0, "embeddings_generated": 0, "errors": 0}

    logger.info(f"Found {len(tables)} tables in schema '{schema}'")

    # schema_embeddings is RLS-enrolled and FORCEd — even the owner needs the
    # tenant GUC set before writing.
    await set_tenant_guc(conn, DEFAULT_TENANT_ID)

    processed = 0
    embeddings = 0
    errors = 0

    for table in tables:
        processed += 1
        embedding_text = build_embedding_text(table)
        columns_json = json.dumps(table["columns"], default=str)

        try:
            if not dry_run:
                # Generate embedding
                embedding_vector = await generate_embedding(embedding_text)
                embeddings += 1

                # Upsert (single transaction per table; embedding API call
                # must not hold a transaction open).
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO schema_embeddings (
                            id, tenant_id, table_schema, table_name,
                            full_name, table_description, columns_json,
                            embedding_text, embedding, created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4,
                            $5, $6, $7,
                            $8, $9::vector(1536), $10, $10
                        )
                        ON CONFLICT (tenant_id, table_schema, table_name)
                        DO UPDATE SET
                            columns_json = EXCLUDED.columns_json,
                            table_description = EXCLUDED.table_description,
                            embedding_text = EXCLUDED.embedding_text,
                            embedding = EXCLUDED.embedding,
                            updated_at = EXCLUDED.updated_at
                        """,
                        str(uuid4()),
                        DEFAULT_TENANT_ID,
                        table["table_schema"],
                        table["table_name"],
                        table["full_name"],
                        table.get("table_description", ""),
                        columns_json,
                        embedding_text,
                        str(embedding_vector),
                        datetime.now(timezone.utc),
                    )

                logger.info(
                    f"Embedded table {table['full_name']} "
                    f"({len(table['columns'])} columns, "
                    f"{len(embedding_vector)}-dim vector)"
                )

        except Exception as e:
            errors += 1
            logger.error(f"Failed to embed table {table['full_name']}: {e}")

    return {
        "tables_processed": processed,
        "embeddings_generated": embeddings,
        "errors": errors,
    }


async def sync_examples(conn, examples_file: str, tenant_id: str = DEFAULT_TENANT_ID) -> int:
    """(Re)seed agent_examples with the golden NL/SQL pairs for few-shot retrieval.

    Idempotent: deletes existing nl2sql examples for the tenant, then inserts
    the golden set with query embeddings. Runs as the owner with the tenant
    GUC set (agent_examples is RLS-enforced).
    """
    from app.core.embeddings import vector_literal

    path = Path(examples_file)
    if not path.is_file():
        logger.error("Examples file not found: %s", path)
        return 0

    cases = json.loads(path.read_text(encoding="utf-8"))
    if not cases:
        logger.warning("Examples file is empty: %s", path)
        return 0

    await set_tenant_guc(conn, tenant_id)
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM agent_examples WHERE agent_name = $1 AND tenant_id = $2::uuid",
            "nl2sql",
            tenant_id,
        )
        for case in cases:
            nl_query = case.get("nl_query", "")
            expected_sql = case.get("expected_sql", "")
            if not nl_query or not expected_sql:
                continue
            embedding = await generate_embedding(nl_query)
            await conn.execute(
                "INSERT INTO agent_examples "
                "(agent_name, nl_query, expected_sql, tags, embedding, tenant_id) "
                "VALUES ($1, $2, $3, $4::jsonb, $5::vector(1536), $6::uuid)",
                "nl2sql",
                nl_query,
                expected_sql,
                json.dumps([case.get("category", "golden")]),
                vector_literal(embedding),
                tenant_id,
            )

    logger.info("Few-shot examples seeded", count=len(cases), tenant=tenant_id)
    return len(cases)


async def _invalidate_caches(tenant_id: str) -> None:
    """Best-effort: drop cached schema context so retrieval sees fresh rows."""
    try:
        from app.core.cache import get_cache

        await get_cache().invalidate_schema(tenant_id)
        logger.info("Schema context cache invalidated", tenant=tenant_id)
    except Exception as e:
        logger.warning("Cache invalidation skipped (non-fatal): %s", e)


async def main():
    parser = argparse.ArgumentParser(
        description="Sync database schema metadata to pgvector embeddings"
    )
    parser.add_argument(
        "--schema", default="public",
        help="Database schema to embed (default: public)",
    )
    parser.add_argument(
        "--domain",
        help="Limit to tables matching this prefix (e.g. 'sales')",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview tables without generating embeddings or writing",
    )
    parser.add_argument(
        "--examples", action="store_true",
        help="Also seed agent_examples with the golden NL/SQL pairs",
    )
    parser.add_argument(
        "--examples-file",
        default=None,
        help="Golden JSON path for --examples "
        "(default: backend/tests/evals/nl2sql_golden.json relative to repo root)",
    )
    parser.add_argument(
        "--connection-url",
        default=None,
        help="Owner PostgreSQL connection URL (default: DATABASE_URL_SYNC)",
    )
    args = parser.parse_args()

    conn = await owner_connect(args.connection_url)
    try:
        logger.info(
            "Starting schema embedding sync",
            schema=args.schema,
            domain=args.domain,
            dry_run=args.dry_run,
        )

        result = await sync_schema(
            conn=conn,
            schema=args.schema,
            dry_run=args.dry_run,
        )

        if args.examples and not args.dry_run:
            examples_file = args.examples_file
            if examples_file is None:
                repo_root = Path(__file__).resolve().parents[1]
                examples_file = str(repo_root / "backend" / "tests" / "evals" / "nl2sql_golden.json")
            await sync_examples(conn, examples_file)
    finally:
        await conn.close()

    logger.info(
        "Schema embedding sync complete",
        tables_processed=result["tables_processed"],
        embeddings_generated=result["embeddings_generated"],
        errors=result["errors"],
    )

    if result["errors"] > 0:
        sys.exit(1)

    if not args.dry_run:
        await _invalidate_caches(DEFAULT_TENANT_ID)


if __name__ == "__main__":
    asyncio.run(main())
