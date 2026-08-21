# ADR 007: Cube-native semantic layer (dropping the dbt tier)

- **Status:** Accepted (2026-08-15)
- **Context:** Phase 9 — Real metric catalog
- **Supersedes:** the dbt MetricFlow design described in earlier revisions of
  `docs/semantic-layer.md` and `semantic/README.md`
- **Related:** ADR 006 (enforced RLS), `semantic/cube/model/`,
  `backend/app/semantic/cube_client.py`

## Context

The original design was a three-tier pipeline: dbt MetricFlow YAML → dbt
manifest → Cube (via `semantic_layer_sync`) → `CubeClient` → agents. Phase 9
planning found every link of that pipeline non-functional:

1. **dbt was never installed** — no dependency in `pyproject.toml`/`uv.lock`,
   no Dockerfile entry, no CI job, no `profiles.yml`; `dbt parse/run` could
   not execute anywhere.
2. **The bridge was fictional** — `semantic_layer_sync` in `cube.js` is a
   Cube Cloud feature, not Cube Core; the manifest it pointed at could never
   be generated.
3. **The toy metric YAML was invalid** — `revenue.yml` referenced measures
   (`user_id`, `conversions`, `total_users`) that no semantic model defined.
4. **The Cube container was unwired** — no volume mounts at all: it could not
   read `cube.js`, any schema, or any manifest.

Meanwhile the consumer side was real and tested: `CubeClient` (719 lines,
393 test lines locking the `/meta` and `/load` contracts), the ChatService →
NL2SQL metric-context injection, and the per-tenant metric cache.

A second constraint: Phase 8b enforced RLS on all analytics tables.
Cube's `cube_reader` role sees **zero rows** without a per-tenant
`app.current_tenant_id` GUC — so Cube *data* queries need driver-level
tenant work regardless of where metric definitions live.

## Decision

1. **Cube-native data models are the single source of truth.** Ten cubes in
   `semantic/cube/model/` over the seeded analytics tables (23 measures:
   revenue, orders, customers, transactions, web users, activity, deals,
   reps, products, regions). Joins only where seed foreign keys are real.
   Every cube carries a hidden `tenant_id` dimension as the Phase-10 hook.
2. **Delete the dbt scaffold** (`semantic/dbt/`) rather than maintain a
   second, unrunnable definition format.
3. **Wire the Cube runtime properly**: standard `CUBEJS_DB_*` env (read-only
   `cube_reader` role), project mounted at `/cube/conf`, `node`-based
   healthcheck.
4. **Scope data queries out**: `/metrics/list` (metadata) ships now;
   `/metrics/query` waits for per-tenant GUC driver work
   (`contextToOrchestratorId` + connection-init SQL) in Phase 10, together
   with the Explore UI.
5. **Harden the client while here**: real JWT auth (was raw secret —
   dev-mode only), cache the raw `/meta` payload and re-parse on hit (the
   old serialization silently dropped parsed metrics), and rank metrics
   against the user query when the catalog exceeds 20 entries.

## Consequences

- One definition format, one runtime, one test surface; the catalog is
  validated by structural tests in CI without Cube or a database.
- "dbt as source of truth" is gone — accepted because nothing consumed dbt
  artifacts and the repo runs no dbt pipeline. If dbt arrives later (tests,
  freshness checks, staging models), Cube can import from it as an addition,
  not a replacement.
- Metric metadata and metric data have different availability: /meta works
  whenever Cube is up; /load additionally requires the Phase-10 tenant
  driver. `CubeClient.query()` callers must not assume tenant-correct
  results until then.
- The NL2SQL agent now receives a real catalog via the same fail-open path —
  Cube being down degrades prompt quality, never availability.
