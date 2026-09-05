"""baseline schema — mirrors infra/postgres/init.sql.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-05

This migration is the Alembic mirror of the schema that init.sql creates on
first Docker boot. Two equally valid paths to a schema'd database:

  1. Docker entrypoint (init.sql) — applies on container creation, then this
     migration is a no-op because every CREATE uses IF NOT EXISTS.
  2. Pure Alembic (fresh DB, no init.sql) — this migration creates everything.

After this baseline, ALL schema changes go through Alembic only (no edits to
init.sql). See docs/adr/005-age-and-pgvector-image.md.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions (idempotent)
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # tenants (control table — not RLS-enrolled)
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.execute(
        "INSERT INTO tenants (id, name) VALUES "
        "('00000000-0000-0000-0000-000000000001', 'default') "
        "ON CONFLICT (id) DO NOTHING"
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("roles", postgresql.JSONB, nullable=False, server_default=sa.text("'[\"user\"]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "email"),
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("input_prompt_hash", sa.String(64), nullable=False),
        sa.Column("generated_sql", sa.Text),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("feedback_score", sa.Integer),
        sa.Column("hallucination_flag", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_audit_log_session", "audit_log", ["session_id"])
    op.create_index("idx_audit_log_tenant", "audit_log", ["tenant_id"])
    op.create_index("idx_audit_log_created", "audit_log", ["created_at"])

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_conversations_tenant", "conversations", ["tenant_id"])

    # schema_embeddings (one row per table; matches embed_schema.py)
    op.create_table(
        "schema_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("table_schema", sa.String(255), nullable=False, server_default=sa.text("'public'")),
        sa.Column("table_name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("table_description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("columns_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("embedding_text", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),  # see note below
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "table_schema", "table_name"),
    )
    # Convert the embedding column to pgvector type if the extension is present.
    # Using ARRAY above keeps the migration portable; this cast makes it a real
    # VECTOR(1536) column where pgvector is installed.
    op.execute(
        "DO $$ BEGIN "
        "  ALTER TABLE schema_embeddings ALTER COLUMN embedding TYPE VECTOR(1536); "
        "EXCEPTION WHEN undefined_object THEN NULL; END $$;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_schema_embeddings_lookup "
        "ON schema_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.create_index("idx_schema_embeddings_tenant", "schema_embeddings", ["tenant_id"])

    # agent_examples
    op.create_table(
        "agent_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("nl_query", sa.Text, nullable=False),
        sa.Column("expected_sql", sa.Text, nullable=False),
        sa.Column("tags", postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.execute(
        "DO $$ BEGIN "
        "  ALTER TABLE agent_examples ALTER COLUMN embedding TYPE VECTOR(1536); "
        "EXCEPTION WHEN undefined_object THEN NULL; END $$;"
    )
    op.create_index("idx_agent_examples_agent", "agent_examples", ["agent_name"])
    op.create_index("idx_agent_examples_tenant", "agent_examples", ["tenant_id"])

    # RLS — every tenant-scoped table. FORCE closes the owner-bypass loophole.
    for tbl in ("users", "audit_log", "conversations", "schema_embeddings", "agent_examples"):
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {tbl} "
            f"USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)"
        )


def downgrade() -> None:
    # Destructive on purpose — Alembic downgrades are explicit and reviewed.
    for tbl in ("agent_examples", "schema_embeddings", "conversations", "audit_log", "users", "tenants"):
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
