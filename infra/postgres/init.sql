-- =============================================================================
-- GenBI Database Initialization
-- =============================================================================
-- This script runs once when the PostgreSQL container is first created.
-- It sets up extensions, roles, and core tables.
-- WARNING: destructive if run on an existing database.

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "age";
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

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

-- Row-level security: users scoped to their tenant
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

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

CREATE INDEX idx_audit_log_session ON audit_log(session_id);
CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    title       VARCHAR(500),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_tenant ON conversations(tenant_id);

-- ---------------------------------------------------------------------------
-- Schema Embeddings (for NL2SQL semantic search)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schema_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name      VARCHAR(255) NOT NULL,
    column_name     VARCHAR(255) NOT NULL,
    description     TEXT,
    embedding       VECTOR(1536),
    tenant_id       UUID REFERENCES tenants(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_schema_embeddings_lookup
    ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

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
    tenant_id       UUID REFERENCES tenants(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_examples_agent ON agent_examples(agent_name);
