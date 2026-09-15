"""Tenant knowledge base — wiki pages, revisions, search (Phase 24, ADR 010).

GUC-writer on the RLS-bound runtime role (``genbi_app``): wiki is business
data, so every connection sets the tenant GUC and RLS enforces isolation at
the database layer.

Model (ADR 010): slug-addressed markdown pages with append-only revisions —
every write appends the next version then updates the page in one
transaction; restore copies an old version FORWARD as a new revision.
History is never rewritten. On every write the page's pgvector chunks are
replaced (fail-open — the page saves fine without an embedding key).

Search: cosine top-k over ``wiki_embeddings`` (asyncpg ``$N`` binds) with a
keyword fallback that fetches pages via a fully static SELECT and filters in
Python — the query never touches SQL text. The NL2SQL hook
(``retrieve_wiki_context``) follows the schema_retrieval fail-open contract.
"""

import uuid
from datetime import UTC, datetime

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger

MAX_SLUG_LEN = 200
MAX_TITLE_LEN = 500
_CHUNK_TARGET = 1500


class PageExistsError(Exception):
    """Another page already uses this slug in this tenant."""


def _dsn() -> str:
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _connect(tenant_id: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
    return conn


# ---------------------------------------------------------------------------
# Chunking + embedding sync (ADR 010 §3)
# ---------------------------------------------------------------------------


def chunk_content(content_md: str, target: int = _CHUNK_TARGET) -> list[str]:
    """Split markdown into ~target-char chunks on paragraph boundaries."""
    text = (content_md or "").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip()
        if current and len(candidate) > target:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def _sync_embeddings(
    conn: asyncpg.Connection, page_id: str, tenant_id: str, content_md: str
) -> bool:
    """Replace the page's chunks. Fail-open (page writes never depend on it)."""
    from app.core.embeddings import embed_text, vector_literal

    try:
        chunks = chunk_content(content_md)
        await conn.execute("DELETE FROM wiki_embeddings WHERE page_id = $1::uuid", page_id)
        for chunk in chunks:
            embedding = await embed_text(chunk)
            await conn.execute(
                "INSERT INTO wiki_embeddings (page_id, tenant_id, chunk, embedding) VALUES ($1::uuid, $2::uuid, $3, CAST($4 AS vector))",
                page_id,
                tenant_id,
                chunk,
                vector_literal(embedding),
            )
        return True
    except Exception as e:  # noqa: BLE001 — knowledge base must save without a key
        logger.warning("Wiki embedding sync skipped (non-fatal): %s", e)
        return False


async def reconcile_embeddings(tenant_id: str) -> int:
    """Re-embed pages whose chunks are missing (best-effort helper)."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT p.id, p.content_md FROM wiki_pages p WHERE NOT EXISTS (SELECT 1 FROM wiki_embeddings e WHERE e.page_id = p.id)",
        )
        for row in rows:
            await _sync_embeddings(conn, str(row["id"]), tenant_id, row["content_md"])
        return len(rows)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def _page_dict(row) -> dict:
    return {
        "slug": row["slug"],
        "title": row["title"],
        "content_md": row["content_md"],
        "parent_slug": row["parent_slug"],
        "updated_by": str(row["updated_by"]),
        "updated_at": row["updated_at"].isoformat(),
        "created_at": row["created_at"].isoformat(),
    }


async def upsert_page(
    tenant_id: str,
    slug: str,
    title: str,
    content_md: str,
    editor_user_id: str,
    parent_slug: str | None = None,
) -> dict:
    """Create or update a page: append revision + update page atomically."""
    conn = await _connect(tenant_id)
    try:
        async with conn.transaction():
            existing = await conn.fetchrow("SELECT id, slug FROM wiki_pages WHERE slug = $1", slug)
            if existing is None:
                page_id = str(uuid.uuid4())
                try:
                    await conn.execute(
                        "INSERT INTO wiki_pages (id, tenant_id, slug, title, content_md, parent_slug, created_by, updated_by) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, $7::uuid)",
                        page_id,
                        tenant_id,
                        slug,
                        title[:MAX_TITLE_LEN],
                        content_md,
                        parent_slug,
                        editor_user_id,
                    )
                except asyncpg.UniqueViolationError as e:
                    raise PageExistsError(f"slug already in use: {slug}") from e
            else:
                page_id = str(existing["id"])
                await conn.execute(
                    "UPDATE wiki_pages SET title = $3, content_md = $4, parent_slug = $5, updated_by = $6::uuid, updated_at = NOW() WHERE slug = $1 AND tenant_id = $2::uuid",
                    slug,
                    tenant_id,
                    title[:MAX_TITLE_LEN],
                    content_md,
                    parent_slug,
                    editor_user_id,
                )

            version = await conn.fetchval(
                "SELECT coalesce(max(version), 0) + 1 FROM wiki_page_revisions WHERE page_id = $1::uuid",
                page_id,
            )
            await conn.execute(
                "INSERT INTO wiki_page_revisions (page_id, tenant_id, version, title, content_md, edited_by) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)",
                page_id,
                tenant_id,
                version,
                title[:MAX_TITLE_LEN],
                content_md,
                editor_user_id,
            )
            row = await conn.fetchrow(
                "SELECT slug, title, content_md, parent_slug, updated_by, updated_at, created_at FROM wiki_pages WHERE slug = $1",
                slug,
            )
    finally:
        await conn.close()

    result = _page_dict(row)
    result["version"] = version
    # Embedding sync after the transaction commits — fail-open by contract.
    sync_conn = await _connect(tenant_id)
    try:
        synced = await _sync_embeddings(sync_conn, page_id, tenant_id, content_md)
    finally:
        await sync_conn.close()
    result["embedded"] = synced
    return result


async def get_page(tenant_id: str, slug: str) -> dict | None:
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT slug, title, content_md, parent_slug, updated_by, updated_at, created_at FROM wiki_pages WHERE slug = $1",
            slug,
        )
    finally:
        await conn.close()
    return _page_dict(row) if row else None


async def delete_page(tenant_id: str, slug: str) -> bool:
    """Delete a page; revisions and chunks cascade. False when not found."""
    conn = await _connect(tenant_id)
    try:
        deleted = await conn.execute("DELETE FROM wiki_pages WHERE slug = $1", slug)
    finally:
        await conn.close()
    return deleted == "DELETE 1"


async def list_pages(tenant_id: str) -> list[dict]:
    """Flat page list (tree assembly happens in the client)."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT slug, title, parent_slug, updated_at FROM wiki_pages ORDER BY title",
        )
    finally:
        await conn.close()
    return [
        {
            "slug": row["slug"],
            "title": row["title"],
            "parent_slug": row["parent_slug"],
            "updated_at": row["updated_at"].isoformat(),
        }
        for row in rows
    ]


async def page_history(tenant_id: str, slug: str) -> list[dict] | None:
    """Revisions newest-first. None when the page does not exist."""
    conn = await _connect(tenant_id)
    try:
        page = await conn.fetchrow("SELECT id FROM wiki_pages WHERE slug = $1", slug)
        if page is None:
            return None
        rows = await conn.fetch(
            "SELECT version, title, edited_by, created_at FROM wiki_page_revisions WHERE page_id = $1::uuid ORDER BY version DESC",
            page["id"],
        )
    finally:
        await conn.close()
    return [
        {
            "version": row["version"],
            "title": row["title"],
            "edited_by": str(row["edited_by"]),
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


async def restore_page(tenant_id: str, slug: str, version: int, editor_user_id: str) -> dict | None:
    """Restore an old revision FORWARD as a new revision. None when the
    page or the version does not exist."""
    conn = await _connect(tenant_id)
    try:
        row = await conn.fetchrow(
            "SELECT r.title, r.content_md FROM wiki_page_revisions r JOIN wiki_pages p ON p.id = r.page_id WHERE p.slug = $1 AND r.version = $2",
            slug,
            version,
        )
    finally:
        await conn.close()
    if row is None:
        return None
    return await upsert_page(
        tenant_id=tenant_id,
        slug=slug,
        title=row["title"],
        content_md=row["content_md"],
        editor_user_id=editor_user_id,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _map_hits(rows) -> list[dict]:
    hits = []
    for row in rows:
        if isinstance(row, dict):
            slug, title, chunk, score = (
                row.get("slug"),
                row.get("title"),
                row.get("chunk"),
                row.get("score"),
            )
        else:
            slug, title, chunk, score = row["slug"], row["title"], row["chunk"], row["score"]
        hits.append(
            {
                "slug": slug,
                "title": title,
                "chunk": (chunk or "")[:500],
                "score": float(score) if score is not None else 0.0,
            }
        )
    return hits


async def _semantic_search(query: str, tenant_id: str, top_k: int) -> list[dict]:
    """pgvector cosine top-k over the tenant's wiki chunks."""
    from app.core.embeddings import embed_text, vector_literal

    embedding = await embed_text(query)
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT p.slug, p.title, e.chunk, 1 - (e.embedding <=> CAST($1 AS vector)) AS score FROM wiki_embeddings e JOIN wiki_pages p ON p.id = e.page_id WHERE e.embedding IS NOT NULL ORDER BY e.embedding <=> CAST($1 AS vector) LIMIT $2",
            vector_literal(embedding),
            top_k,
        )
    finally:
        await conn.close()
    return _map_hits(rows)


async def _keyword_fallback(query: str, tenant_id: str, top_k: int) -> list[dict]:
    """Static SELECT + Python filter — the query never touches SQL text."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT slug, title, content_md AS chunk, 0.0 AS score FROM wiki_pages LIMIT 200",
        )
    finally:
        await conn.close()
    needle = (query or "").lower()
    if not needle:
        return []
    filtered = [
        row
        for row in rows
        if needle in str(row["title"]).lower() or needle in str(row["chunk"]).lower()
    ]
    return _map_hits(filtered[:top_k])


async def search_pages(query: str, tenant_id: str, top_k: int = 5) -> list[dict]:
    """Semantic search with a keyword fallback; empty on total failure."""
    try:
        return await _semantic_search(query, tenant_id, top_k)
    except Exception as e:  # noqa: BLE001 — fall back to keyword search
        logger.warning("Wiki semantic search unavailable — keyword fallback: %s", e)
    try:
        return await _keyword_fallback(query, tenant_id, top_k)
    except Exception as e:  # noqa: BLE001
        logger.warning("Wiki search failed entirely (returning no hits): %s", e)
        return []


async def retrieve_wiki_context(query: str, tenant_id: str, top_k: int = 3) -> list[dict]:
    """NL2SQL hook — the schema_retrieval fail-open contract: hits for the
    ``## Tenant Knowledge`` prompt section, [] on any problem."""
    try:
        return await search_pages(query, tenant_id, top_k=top_k)
    except Exception as e:  # noqa: BLE001
        logger.warning("Wiki context retrieval failed (continuing without): %s", e)
        return []


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
