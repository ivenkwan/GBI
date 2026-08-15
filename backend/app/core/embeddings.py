"""Embedding provider — vector search support for schema/few-shot retrieval.

Uses OpenAI embeddings: `text-embedding-3-small` produces exactly the 1536
dimensions the VECTOR(1536) columns (schema_embeddings, agent_examples)
expect. Anthropic has no public embeddings API — the original
`claude-embeddings-*` call in scripts/embed_schema.py never worked.
"""

from app.core.config import settings
from app.core.logging import logger


async def embed_text(text: str) -> list[float]:
    """Embed a text into a VECTOR(1536)-compatible float list.

    Raises RuntimeError when no API key is configured or the API call fails
    — callers (schema retrieval) fail open and treat this as no context.
    """
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured — embeddings unavailable")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text,
            dimensions=settings.EMBEDDING_DIMS,
        )
    except Exception as e:
        logger.warning("Embedding API call failed: %s", type(e).__name__)
        raise RuntimeError("embedding API call failed") from e

    embedding = response.data[0].embedding
    if len(embedding) != settings.EMBEDDING_DIMS:
        raise RuntimeError(
            f"embedding model returned {len(embedding)} dims, "
            f"expected {settings.EMBEDDING_DIMS} (VECTOR column is fixed-size)"
        )
    return embedding


def vector_literal(embedding: list[float]) -> str:
    """Render an embedding as a Postgres vector literal ('[0.1,0.2,...]')."""
    return "[" + ",".join(str(v) for v in embedding) + "]"
