-- Control-plane RLS + roles for 0008_control_plane (Phase 21, ADR 009).
-- Applied by `make migrate` (after alembic) and by CI. Idempotent.
--
-- genbi_admin is the control-plane role (ADR 009 §3): DML on control-plane
-- tables + SELECT on audit_log, permissive policies scoped TO genbi_admin
-- on exactly those tables. It can read NO business data. genbi_auth is
-- retired here — login moves to genbi_admin, which supersedes its
-- single-table scope (login now also reads platform_admins + tenants).

-- ------------------------------------------------------------------ role --
DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'genbi_admin') THEN
        CREATE ROLE genbi_admin LOGIN PASSWORD 'genbi_admin';
    END IF;
END
$role$;

GRANT USAGE ON SCHEMA public TO genbi_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tenants TO genbi_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.users TO genbi_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.platform_admins TO genbi_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.admin_audit TO genbi_admin;
GRANT SELECT ON public.audit_log TO genbi_admin;

-- --------------------------------------------------------------- tenants --
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_all ON public.tenants;
CREATE POLICY admin_all ON public.tenants
    FOR ALL TO genbi_admin USING (true) WITH CHECK (true);

-- ------------------------------------------------------------------ users --
-- genbi_admin manages users across tenants (provisioning, user CRUD);
-- the old genbi_auth login-lookup carve-out is subsumed by this policy.
DROP POLICY IF EXISTS users_login_lookup ON public.users;
DROP POLICY IF EXISTS admin_all ON public.users;
CREATE POLICY admin_all ON public.users
    FOR ALL TO genbi_admin USING (true) WITH CHECK (true);

-- -------------------------------------------------------- platform_admins --
-- Platform scope: no tenant GUC policy — only genbi_admin may touch it
-- (genbi_app has no grants; RLS is FORCEd so even accidental grants stay
-- inert until a policy exists).
ALTER TABLE public.platform_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_admins FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_all ON public.platform_admins;
CREATE POLICY admin_all ON public.platform_admins
    FOR ALL TO genbi_admin USING (true) WITH CHECK (true);

-- ------------------------------------------------------------ admin_audit --
ALTER TABLE public.admin_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_audit FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_all ON public.admin_audit;
CREATE POLICY admin_all ON public.admin_audit
    FOR ALL TO genbi_admin USING (true) WITH CHECK (true);

-- -------------------------------------------------------------- audit_log --
DROP POLICY IF EXISTS admin_read ON public.audit_log;
CREATE POLICY admin_read ON public.audit_log
    FOR SELECT TO genbi_admin USING (true);

-- ----------------------------------------------------- retire genbi_auth --
DO $retire$
BEGIN
    BEGIN
        DROP POLICY IF EXISTS users_login_lookup ON public.users;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'policy drop skipped: %', SQLERRM;
    END;
    BEGIN
        REVOKE SELECT ON public.users FROM genbi_auth;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'revoke skipped: %', SQLERRM;
    END;
    BEGIN
        -- 0002 also granted schema USAGE; the role cannot drop while it holds it
        REVOKE ALL ON SCHEMA public FROM genbi_auth;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'schema revoke skipped: %', SQLERRM;
    END;
    BEGIN
        DROP ROLE IF EXISTS genbi_auth;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'genbi_auth drop skipped (still has dependencies): %', SQLERRM;
    END;
END
$retire$;

-- ------------------------------------------------------- slug backfill --
-- One-time: derive slugs for existing tenants that have none. Per-row
-- guard so a name collision degrades to a suffix instead of failing.
DO $slug$
DECLARE
    row RECORD;
    candidate TEXT;
    suffix INT := 0;
BEGIN
    FOR row IN SELECT id, name FROM public.tenants WHERE slug IS NULL LOOP
        candidate := substr(lower(regexp_replace(row.name, '[^a-zA-Z0-9]+', '-', 'g')), 1, 50);
        candidate := btrim(candidate, '-');
        WHILE EXISTS (SELECT 1 FROM public.tenants WHERE slug = candidate) LOOP
            suffix := suffix + 1;
            candidate := substr(candidate, 1, 48) || '-' || suffix::text;
        END LOOP;
        UPDATE public.tenants SET slug = candidate WHERE id = row.id;
    END LOOP;
END
$slug$;
