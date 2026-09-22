"""Schema + few-shot retrieval — pgvector semantic search for the NL2SQL agent.

The query text is embedded, then matched against the tenant-scoped
schema_embeddings / agent_examples tables via cosine distance. Reads go
through PostgreSQLConnector as the RLS-bound genbi_app role with the tenant
GUC set per transaction (Phase 8b), so retrieval is tenant-isolated at the
database layer.

When embeddings are unavailable (no embedding API key, DeepSeek-class
chat-only BYOK) or the rows were never vectorized, both retrievals fall
back to lexical ranking over the same rows — keyword overlap instead of
cosine distance. Coarser, but the NL2SQL agent gets real table/column
names instead of hallucinating them.

Everything fails OPEN: no key, no rows, DB unreachable → empty context
and a warning — the pipeline proceeds exactly as it did before this
module existed.
"""

import contextlib
import json
import re

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

# Lexical fallback source rows — bounded because this ranks in Python.
LEXICAL_SCHEMA_SQL = """
    SELECT full_name, table_description, columns_json, embedding_text
    FROM schema_embeddings
    ORDER BY full_name
    LIMIT 100
"""

LEXICAL_EXAMPLES_SQL = """
    SELECT nl_query, expected_sql
    FROM agent_examples
    WHERE agent_name = 'nl2sql'
    ORDER BY nl_query
    LIMIT 100
"""


def _lexical_terms(query: str) -> list[str]:
    """Content words of the query — the lexical-ranking unit."""
    return [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]


def _rank_lexically(
    rows: list[dict], text_keys: tuple[str, ...], terms: list[str], top_k: int
) -> list[dict]:
    """Keyword-overlap ranking over rows already fetched.

    Score = number of query terms present in the row's text fields; ties and
    zero-score rows keep the query's stable (alphabetical) order, so results
    are deterministic. Zero-score rows are still returned — for schema
    context, real table names beat no context.
    """
    scored = [
        (
            sum(
                1
                for t in terms
                if t in " ".join(str(row.get(k) or "") for k in text_keys).lower()
            ),
            row,
        )
        for row in rows
    ]
    scored.sort(key=lambda pair: -pair[0])
    return [row for _, row in scored[:top_k]]


async def retrieve_schema_context(query: str, tenant_id: str, top_k: int = 5) -> list[dict]:
    """Top-k most schema-relevant tables for a query.

    Returns dicts shaped for NL2SQLAgent._build_user_message:
    {"table_name": "public.sales", "description": ..., "columns": [...]}.
    """
    from app.connectors.postgresql_connector import PostgreSQLConnector

    try:
        try:
            embedding = await embed_text(query)
        except Exception as e:
            logger.warning("Schema embedding unavailable — lexical fallback: %s", e)
            embedding = None

        connector = PostgreSQLConnector(connection_url=settings.DATABASE_URL, tenant_id=tenant_id)
        async with connector:
            rows = []
            if embedding is not None:
                rows = await connector.execute(
                    SCHEMA_SEARCH_SQL,
                    params={"emb": vector_literal(embedding), "top_k": top_k},
                )
            if not rows:
                # No vector match (API down, rows never vectorized) — rank
                # the metadata lexically instead.
                candidates = await connector.execute(LEXICAL_SCHEMA_SQL)
                rows = _rank_lexically(
                    candidates,
                    ("full_name", "table_description", "embedding_text"),
                    _lexical_terms(query),
                    top_k,
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
        try:
            embedding = await embed_text(query)
        except Exception as e:
            logger.warning("Example embedding unavailable — lexical fallback: %s", e)
            embedding = None

        connector = PostgreSQLConnector(connection_url=settings.DATABASE_URL, tenant_id=tenant_id)
        async with connector:
            rows = []
            if embedding is not None:
                rows = await connector.execute(
                    FEW_SHOT_SEARCH_SQL,
                    params={"emb": vector_literal(embedding), "top_k": top_k},
                )
            if not rows:
                candidates = await connector.execute(LEXICAL_EXAMPLES_SQL)
                rows = _rank_lexically(
                    candidates,
                    ("nl_query", "expected_sql"),
                    _lexical_terms(query),
                    top_k,
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
