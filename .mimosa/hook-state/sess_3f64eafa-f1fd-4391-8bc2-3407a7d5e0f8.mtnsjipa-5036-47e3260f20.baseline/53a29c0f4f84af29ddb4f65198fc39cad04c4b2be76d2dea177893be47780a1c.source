"""Schema + few-shot retrieval — pgvector semantic search for the NL2SQL agent.

The query text is embedded, then matched against the tenant-scoped
schema_embeddings / agent_examples tables via cosine distance. Reads go
through PostgreSQLConnector as the RLS-bound genbi_app role with the tenant
GUC set per transaction (Phase 8b), so retrieval is tenant-isolated at the
database layer.

Everything fails OPEN: no key, no embeddings rows, DB unreachable → empty
context and a warning — the pipeline proceeds exactly as it did before this
module existed.
"""

import contextlib
import json

from app.core.config import settings
from app.core.embeddings import embed_text, vector_literal
from app.core.logging import logger

# Cosine distance with an explicit cast (CAST, not '::' — SQLAlchemy text()
# treats '::' as an escaped literal colon and breaks the bind); works through
# the connector's named params on plain strings (no pgvector codec needed).
SCHEMA_SEARCH_SQL = """
    SELECT full_name, table_description, columns_json,
           1 - (embedding <=> CAST(:emb AS vector)) AS score
    FROM schema_embeddings
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:emb AS vector)
    LIMIT :top_k
"""

# NOTE: agent_examples has no ivfflat index — this seq-scans, which is fine
# at the current scale (tens of examples); add an index if it grows.
FEW_SHOT_SEARCH_SQL = """
    SELECT nl_query, expected_sql,
           1 - (embedding <=> CAST(:emb AS vector)) AS score
    FROM agent_examples
    WHERE agent_name = 'nl2sql' AND embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:emb AS vector)
    LIMIT :top_k
"""


async def retrieve_schema_context(query: str, tenant_id: str, top_k: int = 5) -> list[dict]:
    """Top-k most schema-relevant tables for a query.

    Returns dicts shaped for NL2SQLAgent._build_user_message:
    {"table_name": "public.sales", "description": ..., "columns": [...]}.
    """
    from app.connectors.postgresql_connector import PostgreSQLConnector

    try:
        embedding = await embed_text(query)
        connector = PostgreSQLConnector(connection_url=settings.DATABASE_URL, tenant_id=tenant_id)
        async with connector:
            rows = await connector.execute(
                SCHEMA_SEARCH_SQL,
                params={"emb": vector_literal(embedding), "top_k": top_k},
            )
    except Exception as e:
        logger.warning("Schema context retrieval unavailable — continuing without: %s", e)
        return []

    context = []
    for row in rows:
        columns = row.get("columns_json") or []
        if isinstance(columns, str):
            with contextlib.suppress(Exception):
                columns = json.loads(columns)
        context.append(
            {
                # full_name ("public.sales") — the prompt demands
                # schema-qualified table names.
                "table_name": row.get("full_name") or row.get("table_name", ""),
                "description": row.get("table_description") or "",
                "columns": columns,
            }
        )

    logger.info("Schema context retrieved", tables=len(context), top_k=top_k)
    return context


async def retrieve_few_shot_examples(query: str, tenant_id: str, top_k: int = 3) -> list[dict]:
    """Most similar validated NL/SQL pairs for few-shot prompting.

    Returns dicts shaped for NL2SQLAgent._build_user_message:
    {"nl_query": ..., "expected_sql": ...}.
    """
    from app.connectors.postgresql_connector import PostgreSQLConnector

    try:
        embedding = await embed_text(query)
        connector = PostgreSQLConnector(connection_url=settings.DATABASE_URL, tenant_id=tenant_id)
        async with connector:
            rows = await connector.execute(
                FEW_SHOT_SEARCH_SQL,
                params={"emb": vector_literal(embedding), "top_k": top_k},
            )
    except Exception as e:
        logger.warning("Few-shot retrieval unavailable — continuing without: %s", e)
        return []

    examples = [
        {"nl_query": row.get("nl_query", ""), "expected_sql": row.get("expected_sql", "")}
        for row in rows
    ]
    logger.info("Few-shot examples retrieved", examples=len(examples), top_k=top_k)
    return examples
