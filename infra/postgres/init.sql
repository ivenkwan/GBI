-- =============================================================================
-- GenBI Database Initialization
-- =============================================================================
-- This script runs once when the PostgreSQL container is first created.
-- It sets up extensions, roles, core tables, and row-level security.
-- WARNING: destructive if run on an existing database.
--
-- Ownership split (see docs/adr/005-age-and-pgvector-image.md):
--   - This script owns: extensions, roles, the seed tenant, RLS policies.
--   - Alembic owns: table DDL (CREATE TABLE / ALTER TABLE).
--   - seed_test_data.py owns: INSERT only (no DDL).

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Apache AGE for the lineage graph. Optional: the image
-- (infra/postgres/Dockerfile) layers AGE onto pgvector. Guard so a missing
-- extension degrades gracefully instead of crashing DB init.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_available_extensions WHERE name = 'age'
    ) THEN
        CREATE EXTENSION IF NOT EXISTS age;
        LOAD 'age';
        SET search_path = ag_catalog, "$user", public;
        RAISE NOTICE 'Apache AGE extension enabled.';
    ELSE
        RAISE NOTICE 'Apache AGE not available — lineage graph disabled (GENBI_ENABLE_AGE controls this).';
    END IF;
END $$;

-- Reset search_path for the rest of the script (AGE sets it above)
SET search_path = "$user", public;

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------

-- Read-only role for the Cube.dev semantic layer (headless BI must never write).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cube_reader') THEN
        CREATE ROLE cube_reader LOGIN PASSWORD 'changeme_cube_reader';
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO cube_reader;
-- Tables granted after they are created (see Alembic baseline migration).
-- Default privilege so future tables in public are readable by Cube:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO cube_reader;

-- AGE: grant the application role access to the graph catalog (dev only).
-- In prod, prefer a dedicated age_admin role.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'age') THEN
        GRANT USAGE ON SCHEMA ag_catalog TO PUBLIC;
        GRANT ALL ON SCHEMA ag_catalog TO PUBLIC;
        RAISE NOTICE 'AGE catalog grants applied.';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Core Tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed a default tenant
INSERT INTO tenants (id, name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'default')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    email       VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    roles       JSONB NOT NULL DEFAULT '["user"]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL,
    user_id             UUID NOT NULL,
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    input_prompt_hash   VARCHAR(64) NOT NULL,
    generated_sql       TEXT,
    model_name          VARCHAR(100) NOT NULL,
    model_version       VARCHAR(50) NOT NULL,
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    latency_ms          DOUBLE PRECISION NOT NULL DEFAULT 0,
    feedback_score      INTEGER,
    hallucination_flag  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    title       VARCHAR(500),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);

-- ---------------------------------------------------------------------------
-- Schema Embeddings (for NL2SQL semantic search)
-- ---------------------------------------------------------------------------
-- Expanded to match scripts/embed_schema.py: one row per TABLE (not per
-- column), holding the full column JSON and the text that was embedded.
-- The embedding is generated from build_embedding_text() in that script.

CREATE TABLE IF NOT EXISTS schema_embeddings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    table_schema        VARCHAR(255) NOT NULL DEFAULT 'public',
    table_name          VARCHAR(255) NOT NULL,
    full_name           VARCHAR(512) NOT NULL,
    table_description   TEXT NOT NULL DEFAULT '',
    columns_json        JSONB NOT NULL DEFAULT '[]',
    embedding_text      TEXT NOT NULL DEFAULT '',
    embedding           VECTOR(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, table_schema, table_name)
);

CREATE INDEX IF NOT EXISTS idx_schema_embeddings_lookup
    ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_tenant
    ON schema_embeddings(tenant_id);

-- ---------------------------------------------------------------------------
-- Agent Examples (few-shot prompts)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_examples (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name      VARCHAR(100) NOT NULL,
    nl_query        TEXT NOT NULL,
    expected_sql    TEXT NOT NULL,
    tags            JSONB DEFAULT '[]',
    embedding       VECTOR(1536),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_examples_agent ON agent_examples(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_examples_tenant ON agent_examples(tenant_id);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
-- Every tenant-scoped table gets a tenant_isolation policy. The session GUC
-- `app.current_tenant_id` is set per-transaction by PostgreSQLConnector from
-- the JWT claim. FORCE is applied so even the table OWNER is subject to RLS
-- (otherwise the owner bypasses the policy and isolation is ineffective).
--
-- NOTE: tenants(id) itself is NOT enrolled — it is a shared control table.

ALTER TABLE users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log          ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE schema_embeddings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_examples     ENABLE ROW LEVEL SECURITY;

ALTER TABLE users              FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log          FORCE ROW LEVEL SECURITY;
ALTER TABLE conversations      FORCE ROW LEVEL SECURITY;
ALTER TABLE schema_embeddings  FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_examples     FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
CREATE POLICY tenant_isolation ON audit_log
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
CREATE POLICY tenant_isolation ON conversations
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
CREATE POLICY tenant_isolation ON schema_embeddings
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
CREATE POLICY tenant_isolation ON agent_examples
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
