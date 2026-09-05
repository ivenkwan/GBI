-- RLS policies + grants for 0007_report_schedules (Phase 19).
-- Applied by `make migrate` (after alembic) and by CI. Idempotent.

ALTER TABLE public.report_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.report_schedules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.report_schedules;
CREATE POLICY tenant_isolation ON public.report_schedules
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);

-- The regeneration scheduler runs outside any tenant context, on the owner
-- role (DATABASE_URL_SYNC): it must see due rows across tenants. genbi_app
-- stays tenant-scoped via the policy above; permissive policies OR together.
DROP POLICY IF EXISTS scheduler_full ON public.report_schedules;
CREATE POLICY scheduler_full ON public.report_schedules
    TO genbi USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.report_schedules TO genbi_app;
