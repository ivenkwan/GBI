# ADR 008: Per-tenant Cube data queries via JWT claims and driver GUC

- **Status:** Accepted (2026-08-15)
- **Context:** Phase 10 — Metrics + Explore
- **Related:** ADR 006 (enforced RLS), ADR 007 (Cube-native semantic layer),
  `semantic/cube/cube.js`, `backend/app/semantic/cube_client.py`

## Context

ADR 007 shipped the metric catalog but deliberately scoped out data
queries: the analytics tables are FORCE-RLS tenant-scoped (ADR 006), and
Cube's `cube_reader` role sets no `app.current_tenant_id` GUC — so `/load`
returned **zero rows** for every tenant. Metadata (`/meta`) was unaffected.
Phase 10 had to make `/api/v1/metrics/query` tenant-correct without
weakening the RLS guarantees.

## Decision

Four links in a chain, each simple:

1. **Backend mints tenant-scoped JWTs.** `CubeClient._auth_token(tenant_id)`
   adds a `tenantId` claim to the standard HS256 token (cached per tenant).
   Cube surfaces JWT claims as `securityContext`. Metadata requests still
   send the anonymous token.
2. **Cube isolates orchestrators by tenant.** `contextToOrchestratorId`
   keys on `securityContext.tenantId`, so each tenant gets its own driver
   pool — connections are never shared across tenants.
3. **The driver sets the RLS GUC.** `driverFactory` builds
   `@cubejs-backend/postgres-driver` (bundled in the cubejs/cube image) from
   `CUBEJS_DB_*` env plus the pg `options` connection parameter:
   `-c app.current_tenant_id=<uuid>` — applied on every pooled connection.
   This is the exact GUC the `tenant_isolation` policies consume.
4. **Postgres RLS remains the enforcement layer.** No tenant filter is
   injected into queries (`queryRewrite` unused): hidden dimensions can't be
   filtered externally, and — decisively — the database, not the query
   builder, decides visibility.

Query results are cached per tenant (`genbi:{tenant}:cube_query:{hash}`,
TTL 300s) in the existing two-tier cache; the cache key covers every
result-affecting parameter.

### Why this is safe to ship without a live Cube to test against

**The failure mode is closed.** If any link in the chain is misconfigured —
claim missing, orchestrator shared, GUC not applied — Postgres RLS returns
zero rows for the query. It can never return another tenant's data, because
the GUC (or its absence) is the only thing that opens the policy, and a
wrong GUC opens nothing. A misconfiguration is *visible* (empty results,
caught by `make verify`'s tenant-scoped query check) rather than *silent*.

## Consequences

- `/api/v1/metrics/query` and the Explore page deliver tenant-correct data
  with isolation enforced at the same layer as every other query path.
- The backend never trusts Cube for authorization — only Postgres.
- Token handling grows a per-tenant cache (bounded: one token per active
  tenant, 1h expiry, refreshed 5 min early).
- `CubeClient.query()` now requires `tenant_id` for meaningful results under
  RLS; the parameter is optional only so metadata-only environments keep
  working.
- The pg `options` mechanism is standard libpq behavior (session GUCs at
  connect), not a Cube-specific extension — if Cube's driver ever changes
  config pass-through, the failure is the closed one above.
