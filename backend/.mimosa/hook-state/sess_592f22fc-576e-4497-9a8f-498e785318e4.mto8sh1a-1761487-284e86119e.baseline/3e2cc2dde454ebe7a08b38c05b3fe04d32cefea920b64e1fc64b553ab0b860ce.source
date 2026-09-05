"""tenant_llm — per-tenant BYOK LLM provider configuration.

Revision ID: 0012_tenant_llm
Revises: 0011_wiki
Create Date: 2026-09-05

Phase 25 (ADR 011): one active provider per tenant — provider type
(anthropic | openai), optional gateway base_url, per-role model names, an
optional embedding model (openai only), the pgcrypto-encrypted API key
(never plaintext — see the paired rls file's app_crypto schema), key
display metadata (last4 + version for cache invalidation), and a status
kill switch. audit_log gains provider/key_source/key_version for per-tenant
spend attribution.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_tenant_llm"
down_revision: str | None = "0011_wiki"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_llm_providers",
        sa.Column("tenant_id", sa.UUID(), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("reasoning_model", sa.String(100), nullable=False),
        sa.Column("fast_model", sa.String(100), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("api_key_enc", sa.Text(), nullable=False),
        sa.Column("key_last4", sa.String(4), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint("provider IN ('anthropic', 'openai')", name="ck_tenant_llm_provider"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_tenant_llm_status"),
    )

    # Spend attribution (ADR 011 §8): provider + key_source on every audit row.
    op.add_column("audit_log", sa.Column("provider", sa.String(20), nullable=True))
    op.add_column("audit_log", sa.Column("key_source", sa.String(10), nullable=True))
    op.add_column("audit_log", sa.Column("key_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_log", "key_version")
    op.drop_column("audit_log", "key_source")
    op.drop_column("audit_log", "provider")
    op.drop_table("tenant_llm_providers")
