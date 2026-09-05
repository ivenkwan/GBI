-- Wiki RLS + grants + ivfflat index for 0011_wiki (Phase 24, ADR 010).
-- Applied by `make migrate` (after alembic) and by CI. Idempotent.

-- ------------------------------------------------------------- wiki_pages --
ALTER TABLE public.wiki_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wiki_pages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.wiki_pages;
CREATE POLICY tenant_isolation ON public.wiki_pages
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wiki_pages TO genbi_app;

-- ---------------------------------------------------- wiki_page_revisions --
ALTER TABLE public.wiki_page_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wiki_page_revisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.wiki_page_revisions;
CREATE POLICY tenant_isolation ON public.wiki_page_revisions
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wiki_page_revisions TO genbi_app;

-- ------------------------------------------------------- wiki_embeddings --
ALTER TABLE public.wiki_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wiki_embeddings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.wiki_embeddings;
CREATE POLICY tenant_isolation ON public.wiki_embeddings
    USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wiki_embeddings TO genbi_app;

-- ivfflat cosine index for retrieval (structured ops can't express this).
DROP INDEX IF EXISTS idx_wiki_embeddings_vector;
CREATE INDEX idx_wiki_embeddings_vector
    ON public.wiki_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
