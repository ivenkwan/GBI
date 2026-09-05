-- BYOK storage RLS + crypto seam for 0012_tenant_llm (Phase 25, ADR 011).
-- Applied by `make migrate` (after alembic) and by CI. Idempotent.

-- ------------------------------------------------------------- pgcrypto ---
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------- app_crypto ---
-- SECURITY DEFINER encrypt/decrypt wrapping pgp_sym_*: the key rides as the
-- $1 bind parameter from TENANT_ENCRYPTION_KEY — never in DDL, never in a
-- SQL literal, never in a log. Python never constructs ciphertext; the
-- ciphertext column only ever receives the function's output as a bind.
CREATE SCHEMA IF NOT EXISTS app_crypto;

CREATE OR REPLACE FUNCTION app_crypto.encrypt(p_key text, p_plaintext text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
    SELECT encode(pgp_sym_encrypt(p_plaintext, p_key, 'cipher-algo=aes256'), 'base64')
$fn$;

CREATE OR REPLACE FUNCTION app_crypto.decrypt(p_key text, p_ciphertext text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
    SELECT pgp_sym_decrypt(decode(p_ciphertext, 'base64'), p_key)
$fn$;

REVOKE ALL ON FUNCTION app_crypto.encrypt(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_crypto.decrypt(text, text) FROM PUBLIC;
GRANT USAGE ON SCHEMA app_crypto TO genbi_app;
GRANT EXECUTE ON FUNCTION app_crypto.encrypt(text, text) TO genbi_app;
GRANT EXECUTE ON FUNCTION app_crypto.decrypt(text, text) TO genbi_app;

-- ------------------------------------------------- tenant_llm_providers ---
-- Standard tenant recipe: the runtime role sees only its tenant's rows
-- through the GUC. The secret column never leaves the database encrypted.
ALTER TABLE public.tenant_llm_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_llm_providers FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.tenant_llm_providers;
CREATE POLICY tenant_isolation ON public.tenant_llm_providers
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tenant_llm_providers TO genbi_app;

-- audit_log new columns are nullable — no grant changes needed.
