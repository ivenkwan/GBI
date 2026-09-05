-- RLS policies + grants for 0006_dashboards (Phase 18).
-- Applied by `make migrate` (after alembic) and by CI. Idempotent.

ALTER TABLE public.dashboards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dashboards FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.dashboards;
CREATE POLICY tenant_isolation ON public.dashboards
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

ALTER TABLE public.dashboard_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dashboard_sections FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.dashboard_sections;
CREATE POLICY tenant_isolation ON public.dashboard_sections
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.dashboards TO genbi_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.dashboard_sections TO genbi_app;
