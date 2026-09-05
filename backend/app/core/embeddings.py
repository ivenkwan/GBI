"""Embedding provider — vector search support for schema/few-shot retrieval.

Uses OpenAI embeddings: `text-embedding-3-small` produces exactly the 1536
dimensions the VECTOR(1536) columns (schema_embeddings, agent_examples)
expect. Anthropic has no public embeddings API — the original
`claude-embeddings-*` call in scripts/embed_schema.py never worked.

BYOK (Phase 25, ADR 011 §9): when the tenant's provider is openai and an
embedding_model is configured, embeddings ride the tenant's key and model;
otherwise the platform OpenAI key stays in force. Fail-open unchanged.
"""

from app.core.config import settings
from app.core.logging import logger


async def embed_text(text: str, tenant_id: str | None = None) -> list[float]:
    """Embed a text into a VECTOR(1536)-compatible float list.

    Raises RuntimeError when no API key is configured or the API call fails
    — callers (schema retrieval) fail open and treat this as no context.
    """
    api_key = settings.OPENAI_API_KEY
    model = settings.EMBEDDING_MODEL
    base_url = None

    if tenant_id:
        try:
            from app.llm.resolver import resolve_llm

            resolved = await resolve_llm(tenant_id)
            if resolved.provider == "openai" and resolved.embedding_model:
                api_key = resolved.api_key
                model = resolved.embedding_model
                base_url = resolved.base_url
        except Exception as e:  # noqa: BLE001 — fail-open to the platform key
            logger.warning("BYOK embedding resolution unavailable — platform key: %s", e)

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured — embeddings unavailable")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        response = await client.embeddings.create(
            model=model,
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
