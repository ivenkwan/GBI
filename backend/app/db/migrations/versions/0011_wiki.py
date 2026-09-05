"""wiki — tenant knowledge base (pages, revisions, embeddings).

Revision ID: 0011_wiki
Revises: 0010_tenant_users
Create Date: 2026-09-05

Phase 24 (ADR 010): slug-addressed markdown pages with append-only
revision history and pgvector chunks for NL2SQL retrieval. Full tenant
recipe; RLS policies + grants live in the paired
``infra/postgres/rls/0011_wiki_rls.sql`` (including the ivfflat index,
which structured ops cannot express).

(Numbering note: the Phase 24 design said 0009, but 0010_tenant_users
landed first — wiki takes the next slot.)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0011_wiki"
down_revision: str | None = "0010_tenant_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("parent_slug", sa.String(200), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=False),
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
        sa.UniqueConstraint("tenant_id", "slug", name="uq_wiki_pages_tenant_slug"),
    )
    op.create_index("idx_wiki_pages_tenant", "wiki_pages", ["tenant_id"])

    op.create_table(
        "wiki_page_revisions",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("edited_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("page_id", "version", name="uq_wiki_revisions_page_version"),
    )
    op.create_index("idx_wiki_revisions_page", "wiki_page_revisions", ["page_id"])

    op.create_table(
        "wiki_embeddings",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("chunk", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_wiki_embeddings_page", "wiki_embeddings", ["page_id"])
    op.create_index("idx_wiki_embeddings_tenant", "wiki_embeddings", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("wiki_embeddings")
    op.drop_table("wiki_page_revisions")
    op.drop_table("wiki_pages")
