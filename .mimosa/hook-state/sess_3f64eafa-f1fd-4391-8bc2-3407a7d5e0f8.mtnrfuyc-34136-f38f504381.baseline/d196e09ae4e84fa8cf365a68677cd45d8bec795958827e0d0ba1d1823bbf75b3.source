"""Conversation persistence — multi-turn chat history (Phase 14).

Reads and writes go through dedicated asyncpg connections on the RLS-bound
runtime role (genbi_app) with the tenant GUC set per connection — the same
isolation pattern as the audit writer (Phase 12). Per-user scoping beyond
RLS (a tenant's users only see their own conversations) is enforced with
explicit parameterized predicates.

Failure semantics:
- writes (create/append) FAIL OPEN — persistence problems never break a chat
  response; the caller falls back to an in-memory conversation id.
- reads RAISE — callers decide (ChatService history: fail-open to []; the
  conversations API maps failures to 503).
"""

import uuid

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.logging import logger

MAX_TITLE_LEN = 500


def _dsn() -> str:
    """asyncpg DSN for the runtime role (DATABASE_URL, plain driver)."""
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _connect(tenant_id: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", tenant_id)
    return conn


async def create_conversation(user_id: str, tenant_id: str, title: str | None) -> str | None:
    """Create a conversation row. Returns its id, or None on failure."""
    conversation_id = str(uuid.uuid4())
    try:
        conn = await _connect(tenant_id)
        try:
            await conn.execute(
                "INSERT INTO conversations (id, user_id, tenant_id, title) "
                "VALUES ($1::uuid, $2::uuid, $3::uuid, $4)",
                conversation_id,
                user_id,
                tenant_id,
                (title or "New chat")[:MAX_TITLE_LEN],
            )
        finally:
            await conn.close()
        return conversation_id
    except Exception as e:
        logger.warning("Conversation create failed (non-fatal): %s", e)
        return None


async def append_message(
    conversation_id: str,
    tenant_id: str,
    role: str,
    content: str,
    generated_sql: str | None = None,
) -> None:
    """Append one chat turn and bump the conversation's updated_at. Fail-open."""
    try:
        conn = await _connect(tenant_id)
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO messages (conversation_id, tenant_id, role, content, generated_sql) "
                    "VALUES ($1::uuid, $2::uuid, $3, $4, $5)",
                    conversation_id,
                    tenant_id,
                    role,
                    content,
                    generated_sql,
                )
                await conn.execute(
                    "UPDATE conversations SET updated_at = NOW() WHERE id = $1::uuid",
                    conversation_id,
                )
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Message append failed (non-fatal): %s", e)


async def list_conversations(user_id: str, tenant_id: str, limit: int = 50) -> list[dict]:
    """The user's conversations, most recently active first."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations WHERE user_id = $1::uuid "
            "ORDER BY updated_at DESC LIMIT $2",
            user_id,
            limit,
        )
    finally:
        await conn.close()
    return [
        {
            "id": str(row["id"]),
            "title": row["title"] or "New chat",
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
        for row in rows
    ]


async def list_messages(conversation_id: str, tenant_id: str, limit: int = 20) -> list[dict]:
    """The conversation's most recent turns, in chronological order."""
    conn = await _connect(tenant_id)
    try:
        rows = await conn.fetch(
            "SELECT role, content, generated_sql, created_at "
            "FROM messages WHERE conversation_id = $1::uuid "
            "ORDER BY created_at DESC LIMIT $2",
            conversation_id,
            limit,
        )
    finally:
        await conn.close()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "generated_sql": row["generated_sql"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in reversed(rows)
    ]
