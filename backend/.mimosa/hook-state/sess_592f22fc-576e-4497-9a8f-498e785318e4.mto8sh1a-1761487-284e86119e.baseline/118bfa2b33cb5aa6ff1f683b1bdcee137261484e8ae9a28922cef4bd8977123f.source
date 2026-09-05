"""conversations messages — persisted multi-turn chat history.

Revision ID: 0004_messages
Revises: 0003_analytics
Create Date: 2026-08-15

The conversations table existed since the baseline but had nowhere to store
turns; conversation_id round-tripped through the chat API unused. This
migration adds the messages table (RLS-enforced like every tenant table)
that backs Phase 14: history replay in the UI and "## Conversation History"
injection into the NL2SQL prompt.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_messages"
down_revision: str | None = "0003_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            generated_sql TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON public.messages(conversation_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_tenant ON public.messages(tenant_id)")
    op.execute("ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.messages FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.messages")
    op.execute(
        "CREATE POLICY tenant_isolation ON public.messages "
        "USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)"
    )
    # genbi_app already holds DML on tenant tables via 0002's grant list —
    # messages postdates it, so grant explicitly (plus default privileges
    # cover future tables from 0002 onward; this is belt-and-braces).
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.messages TO genbi_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.messages CASCADE")
