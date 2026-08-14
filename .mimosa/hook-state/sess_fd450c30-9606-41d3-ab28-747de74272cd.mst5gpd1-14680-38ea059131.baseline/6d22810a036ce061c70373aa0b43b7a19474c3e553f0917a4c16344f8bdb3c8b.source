"""Schema embedding pipeline — nightly sync of database schema to pgvector.

Generates embeddings for all table/column metadata and stores them in the
schema_embeddings table for semantic search by NL2SQLAgent.

Usage:
    uv run python scripts/embed_schema.py                # full sync
    uv run python scripts/embed_schema.py --domain sales  # single domain
    uv run python scripts/embed_schema.py --dry-run       # preview without writing
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.logging import logger
from app.connectors.postgresql_connector import PostgreSQLConnector


async def get_schema_metadata(
    connector: PostgreSQLConnector,
    schema: str = "public",
) -> list[dict[str, Any]]:
    """Retrieve all table and column metadata from information_schema.

    Returns a list of dicts with:
        - table_name, table_schema
        - column_name, data_type, is_nullable, ordinal_position
        - column_description (from pg_catalog.pg_description or dbt schema.yml)
    """
    query = """
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
    """

    async with connector:
        rows = await connector.execute(query, params=[schema])

    # Group columns by table
    tables: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        if key not in tables:
            tables[key] = {
                "table_schema": row["table_schema"],
                "table_name": row["table_name"],
                "full_name": key,
                "table_description": row.get("table_description") or "",
                "columns": [],
            }

        tables[key]["columns"].append({
            "column_name": row["column_name"],
            "data_type": row["data_type"],
            "udt_name": row["udt_name"],
            "is_nullable": row["is_nullable"],
            "ordinal_position": row["ordinal_position"],
            "description": row.get("column_description") or "",
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

    Uses Anthropic's embeddings API via the LLM client.

    Returns:
        List of floats — the embedding vector.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = await client.embeddings.create(
        model="claude-embeddings-20250219",
        input=text,
    )

    return response.embeddings[0].embedding


async def sync_schema(
    connector: PostgreSQLConnector,
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
    tables = await get_schema_metadata(connector, schema)

    if not tables:
        logger.warning(f"No tables found in schema '{schema}'")
        return {"tables_processed": 0, "embeddings_generated": 0, "errors": 0}

    logger.info(f"Found {len(tables)} tables in schema '{schema}'")

    processed = 0
    embeddings = 0
    errors = 0
    now = datetime.now(timezone.utc)

    for table in tables:
        processed += 1
        embedding_text = build_embedding_text(table)
        columns_json = json.dumps(table["columns"], default=str)

        try:
            if not dry_run:
                # Generate embedding
                embedding_vector = await generate_embedding(embedding_text)
                embeddings += 1

                # Upsert into schema_embeddings
                upsert_sql = """
                    INSERT INTO schema_embeddings (
                        id, tenant_id, table_schema, table_name,
                        full_name, table_description, columns_json,
                        embedding_text, embedding, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9::vector(1536), $10
                    )
                    ON CONFLICT (tenant_id, table_schema, table_name)
                    DO UPDATE SET
                        columns_json = EXCLUDED.columns_json,
                        embedding_text = EXCLUDED.embedding_text,
                        embedding = EXCLUDED.embedding,
                        updated_at = EXCLUDED.updated_at
                """

                await connector.execute(
                    upsert_sql,
                    params=[
                        str(uuid4()),
                        "00000000-0000-0000-0000-000000000001",  # default tenant
                        table["table_schema"],
                        table["table_name"],
                        table["full_name"],
                        table.get("table_description", ""),
                        columns_json,
                        embedding_text,
                        embedding_vector,
                        now,
                    ],
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
        "--connection-url",
        default=settings.DATABASE_URL,
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()

    connector = PostgreSQLConnector(connection_url=args.connection_url)

    logger.info(
        "Starting schema embedding sync",
        schema=args.schema,
        domain=args.domain,
        dry_run=args.dry_run,
    )

    result = await sync_schema(
        connector=connector,
        schema=args.schema,
        dry_run=args.dry_run,
    )

    logger.info(
        "Schema embedding sync complete",
        tables_processed=result["tables_processed"],
        embeddings_generated=result["embeddings_generated"],
        errors=result["errors"],
    )

    if result["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
