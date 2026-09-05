-- AGE lineage functions (Phase 17).
-- Applied on fresh volumes by docker-entrypoint-initdb.d (after init.sql)
-- and on existing databases by `make lineage-setup`.
--
-- The runtime role (genbi_app) cannot LOAD 'age' (superuser-only) and the
-- graph owner must create labels, so each lineage operation is a SECURITY
-- DEFINER function owned by the database owner. genbi_app calls
-- `SELECT app_lineage.fn($1::ag_catalog.agtype)` with ordinary
-- parameterized SQL.
--
-- Two AGE 1.6 rules shape every function here (verified live):
--   * the second cypher() argument must be a dollar-quoted constant, so
--     values can never be spliced into the query text;
--   * the third argument must be a parameter — inside a LANGUAGE sql
--     function the input argument (p_params) IS that parameter, so the
--     values ride the agtype params map exactly as they do from a driver.
--
-- Each function pins search_path to ag_catalog: without it AGE's operators
-- (@>, =) do not resolve.

LOAD 'age';

DO $bootstrap$
BEGIN
    BEGIN
        PERFORM ag_catalog.create_graph('genbi_graph');
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'create_graph skipped: %', SQLERRM;
    END;
END
$bootstrap$;

SET search_path = ag_catalog, public;

DO $labels$
DECLARE
    vlabel text;
    elabel text;
BEGIN
    FOREACH vlabel IN ARRAY ARRAY['Table', 'Column', 'Metric', 'Dashboard', 'User'] LOOP
        BEGIN
            PERFORM ag_catalog.create_vlabel('genbi_graph', vlabel::name);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'vlabel % skipped: %', vlabel, SQLERRM;
        END;
    END LOOP;
    FOREACH elabel IN ARRAY ARRAY['TABLE_CONTAINS', 'METRIC_SOURCE', 'METRIC_DEPENDS',
                                  'DASHBOARD_USES', 'USER_CAN_ACCESS', 'TABLE_JOINS'] LOOP
        BEGIN
            PERFORM ag_catalog.create_elabel('genbi_graph', elabel::name);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'elabel % skipped: %', elabel, SQLERRM;
        END;
    END LOOP;
END
$labels$;

-- AGE's cypher() parser hook must be active in every backend session that
-- plans a cypher call, and LOAD is superuser-only — so attach it to the
-- runtime role itself.
ALTER ROLE genbi_app SET session_preload_libraries = 'age';

CREATE SCHEMA IF NOT EXISTS app_lineage;
GRANT USAGE ON SCHEMA app_lineage TO genbi_app;

-- CREATE OR REPLACE cannot change a return type, so drop first (a no-op
-- notice on first apply). All functions are stateless — nothing is lost.
DROP FUNCTION IF EXISTS app_lineage.merge_table(agtype);
DROP FUNCTION IF EXISTS app_lineage.merge_user_access(agtype);
DROP FUNCTION IF EXISTS app_lineage.merge_metric(agtype);
DROP FUNCTION IF EXISTS app_lineage.upsert_dashboard(agtype);
DROP FUNCTION IF EXISTS app_lineage.clear_dashboard_edges(agtype);
DROP FUNCTION IF EXISTS app_lineage.merge_dashboard_edge(agtype);
DROP FUNCTION IF EXISTS app_lineage.table_impact(agtype);
DROP FUNCTION IF EXISTS app_lineage.metric_sources(agtype);
DROP FUNCTION IF EXISTS app_lineage.metric_dashboards(agtype);

-- ---------------------------------------------------------------- writers --

CREATE OR REPLACE FUNCTION app_lineage.merge_table(p_params agtype)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT * FROM ag_catalog.cypher('genbi_graph',
        $$ MERGE (t:Table { name: $name }) RETURN t.name AS n $$,
        p_params)
    AS (n agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.merge_user_access(p_params agtype)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT * FROM ag_catalog.cypher('genbi_graph',
        $$ MERGE (u:User { user_id: $uid, tenant_id: $tenant })
           WITH u MATCH (t:Table { name: $name })
           MERGE (u)-[e:USER_CAN_ACCESS]->(t)
           SET e.role = $role, e.granted_at = $granted
           RETURN e.role AS n $$,
        p_params)
    AS (n agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.merge_metric(p_params agtype)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT * FROM ag_catalog.cypher('genbi_graph',
        $$ MERGE (m:Metric { name: $name }) RETURN m.name AS n $$,
        p_params)
    AS (n agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.upsert_dashboard(p_params agtype)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT * FROM ag_catalog.cypher('genbi_graph',
        $$ MERGE (d:Dashboard { id: $id }) SET d.name = $name RETURN d.id AS n $$,
        p_params)
    AS (n agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.clear_dashboard_edges(p_params agtype)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT * FROM ag_catalog.cypher('genbi_graph',
        $$ MATCH (d:Dashboard { id: $id })-[old:DASHBOARD_USES]->() DELETE old $$,
        p_params)
    AS (n agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.merge_dashboard_edge(p_params agtype)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT * FROM ag_catalog.cypher('genbi_graph',
        $$ MATCH (d:Dashboard { id: $id })
           MERGE (m:Metric { name: $metric })
           MERGE (d)-[e:DASHBOARD_USES]->(m)
           SET e.position = $position $$,
        p_params)
    AS (n agtype);
$fn$;

-- ---------------------------------------------------------------- readers --
-- agtype columns are returned as text (JSON-encoded); the service parses
-- them defensively.

CREATE OR REPLACE FUNCTION app_lineage.table_impact(p_params agtype)
RETURNS TABLE(table_name text, metric_name text, dashboards text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT t_name::text, m_name::text, d_names::text
    FROM ag_catalog.cypher('genbi_graph',
        $$ MATCH (t:Table { name: $name })-[:TABLE_CONTAINS]->(c:Column)
           <-[:METRIC_SOURCE]-(m:Metric)-[:DASHBOARD_USES]-(d:Dashboard)
           RETURN t.name AS t_name, m.name AS m_name,
                  collect(d.name) AS d_names $$,
        p_params)
    AS (t_name agtype, m_name agtype, d_names agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.metric_sources(p_params agtype)
RETURNS TABLE(table_name text, column_name text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT t_name::text, c_name::text
    FROM ag_catalog.cypher('genbi_graph',
        $$ MATCH (m:Metric { name: $name })-[:METRIC_SOURCE]->(c:Column)
           <-[:TABLE_CONTAINS]-(t:Table)
           RETURN t.name AS t_name, c.name AS c_name $$,
        p_params)
    AS (t_name agtype, c_name agtype);
$fn$;

CREATE OR REPLACE FUNCTION app_lineage.metric_dashboards(p_params agtype)
RETURNS TABLE(dashboard_name text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ag_catalog, public
AS $fn$
    SELECT d_name::text
    FROM ag_catalog.cypher('genbi_graph',
        $$ MATCH (d:Dashboard)-[:DASHBOARD_USES]->(m:Metric { name: $name })
           RETURN d.name AS d_name $$,
        p_params)
    AS (d_name agtype);
$fn$;

GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app_lineage TO genbi_app;
