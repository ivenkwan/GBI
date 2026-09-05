# GenBI Platform — Build Progress

> **Last updated:** 2026-09-05 | **Stack tier:** Enterprise | **132/138 shipped (Phases 1–25) · Phase 26 planned (BYOK APIs/UX — ADR 011)**

---

## Phase 1 — Scaffolding (Tasks 1–10)

| # | Task | Status |
|---|---|---|
| 1 | Root project configuration (CLAUDE.md, .claude/rules, .claude/skills) | ✅ |
| 2 | Backend directory structure (FastAPI, agents, services, models, connectors) | ✅ |
| 3 | Frontend directory structure (Next.js 15 App Router, shadcn/ui base) | ✅ |
| 4 | Semantic layer structure (dbt MetricFlow + Cube.dev) | ✅ |
| 5 | Infrastructure config (Docker Compose, PostgreSQL init, CI) | ✅ |
| 6 | .claude/ rules and skills (api-design, llm-patterns, sql-safety) | ✅ |
| 7 | Documentation (ADR records, OpenAPI specs) | ✅ |
| 8 | Flint Chart integration module (ChartAssemblyInput bridge) | ✅ |
| 9 | Final structure verification (85 files across 7 top-level dirs) | ✅ |
| 10 | Finished Phase 1 | ✅ |

---

## Phase 2 — Core Pipeline (Tasks 11–18)

| # | Task | Status |
|---|---|---|
| 11 | NL2SQLAgent with pgvector schema embedding retrieval | ✅ |
| 12 | ValidationAgent with SQL safety gate (read-only enforcement) | ✅ |
| 13 | NarrativeAgent for data storytelling and insight generation | ✅ |
| 14 | Centralized LLM client with timeout, retry, and audit logging | ✅ |
| 15 | PostgreSQL connector with read-only enforcement and parameterized queries | ✅ |
| 16 | Cube.dev semantic layer client — async REST client with metric formatting for LLM context | ✅ |
| 17 | PII masking for column-level data protection (per-tenant, role-aware) | ✅ |
| 18 | End-to-end chat pipeline (NL → SQL → Chart → Narrative → AuditLog) | ✅ |

---

## Phase 3 — Infrastructure & Quality (Tasks 19–23)

| # | Task | Status |
|---|---|---|
| 19 | Schema embedding pipeline — nightly pgvector sync from information_schema | ✅ |
| 20 | Golden NL2SQL evaluation suite — 20 queries, 3 tolerance levels, 90% threshold | ✅ |
| 21 | LLM mock fixtures for all agent tests | ✅ |
| 22 | OpenTelemetry + Langfuse observability (7 counters/histograms, Prometheus endpoint) | ✅ |
| 23 | CI/CD pipeline — GitHub Actions with lint, test, eval gate, and Docker build | ✅ |

---

## Phase 4 — Frontend & Streaming (Tasks 24–28)

| # | Task | Status |
|---|---|---|
| 24 | Frontend app shell with Next.js App Router, shadcn/ui, and auth guard | ✅ |
| 25 | Zod validation, JWT auth flow, 11 shadcn/ui components, SSE streaming chat UI | ✅ |
| 26 | Apache AGE graph database — 5 vertex labels, 6 edge types, openCypher lineage and impact analysis | ✅ |
| 27 | Test data infrastructure — 10 tables with synthetic generators, multi-tenant seed script | ✅ |
| 28 | Progressive SSE streaming pipeline — start → intent → sql → validation → data → chart → narrative → done | ✅ |

---

## Phase 5 — Performance & Safety (Tasks 29–30)

| # | Task | Status |
|---|---|---|
| 29 | Redis caching layer — L1 (in-memory LRU) + L2 (Redis), typed get/set for schema, metrics, results, charts, LLM responses, sessions, and rate limits | ✅ |
| 30 | Chart hallucination detection — 6 validation categories (field existence, type compatibility, data ranges, null handling, structural validity) with auto-correction engine | ✅ |

---

## Integration Map

```
User Query
  → RouterAgent (intent classification)
    → NL2SQLAgent (metric context from Cube.dev, cached at L2)
      → ValidationAgent (SQL safety gate)
        → Connector (read-only execution, results cached at L1+L2)
          → ChartGenAgent → ChartValidator (hallucination check + auto-correct, spec cached at L2)
            → NarrativeAgent (insight paragraph)
              → AuditLog (persist trace)
```

## Key files delivered

| File | Lines | Purpose |
|---|---|---|
| `backend/app/core/cache.py` | 488 | Dual-tier Redis + in-memory caching service |
| `backend/app/agents/validation/chart_validator.py` | 487 | Deterministic chart hallucination detector |
| `backend/app/services/chat_service.py` | 593 | Full pipeline orchestrator with caching and validation |
| `backend/app/semantic/cube_client.py` | 731 | Cube.dev REST API client with metric-to-LLM formatting |
| `backend/app/db/graph_schema.py` | 447 | Apache AGE lineage graph (openCypher) |
| `backend/app/agents/chart_gen_agent.py` | 204 | Flint MCP chart spec generator |
| `frontend/src/components/chat/chat-view.tsx` | — | Streaming chat UI with SSE consumption |
| `scripts/embed_schema.py` | — | Nightly pgvector schema sync |
| `scripts/seed_test_data.py` | 509 | 10-table synthetic test data generator |

---

## Phase 5b — Environment Provisioning & Bootstrap (new)

> ✅ **STATUS: VERIFIED 2026-08-06.** Closed by Phase 7 Tasks 1–3. Build,
> test run, and `make verify` all green; see Phase 7 for details.

> **Added:** 2026-08-05. Goal: a single `make setup && make up` (or one shell
> script) takes a clean machine to a fully running platform — all services
> healthy, dependencies installed, DB migrated and seeded, secrets generated,
> smoke test green. Today this is impossible: the platform will not boot
> end-to-end as committed. Every defect below is verified against the tree.

| # | Task | Severity | Status |
|---|---|---|---|
| 1 | Author one-command bootstrap script (`scripts/setup.sh`) + Makefile | 🔴 Blocker | ✅ |
| 2 | Fix the AGE-on-pgvector image problem so `init.sql` stops failing | 🔴 Blocker | ✅ |
| 3 | Add the missing config/lock files the Dockerfiles require | 🔴 Blocker | ✅ |
| 4 | Add `alembic.ini` + first migration; reconcile the three schema sources | 🔴 Blocker | ✅ |
| 5 | Healthchecks + dependency ordering on every compose service | 🟠 High | ✅ |
| 6 | Generated `.env` files with random secrets; `make secrets` helper | 🟠 High | ✅ |
| 7 | Postgres role for Apache AGE + Cube dev config | 🟠 Medium | ✅ |
| 8 | `make verify` smoke test (health endpoints + DB round-trip) | 🟠 Medium | ✅ |

---

### Task 1 — One-command bootstrap (`scripts/setup.sh` + `Makefile`)

**Why it matters:** No bootstrap exists today (no `Makefile`, no `setup.sh`,
no `bootstrap.*`). A new contributor must read 5 docs and still hits failures.
CLAUDE.md §5 lists commands but assumes a working environment.

**Deliverable — `Makefile` at repo root with these targets** (each idempotent):
```make
.PHONY: setup up down logs ps verify clean secrets migrate seed reset help

setup:           ## First-time: check prereqs, gen secrets, install deps, build
	up:             ## Start dev stack (docker compose up -d)
	down:           ## Stop dev stack
	logs:           ## Tail logs
	ps:             ## Show service status
	verify:         ## Health + smoke checks (Task 8)
	secrets:        ## Regenerate .env secrets
	migrate:        ## Run alembic upgrade head inside backend
	seed:           ## Load synthetic test data
	reset:          ## down -v && up (NUKES data)
	clean:          ## down -v, prune images, remove node_modules/.venv
	help:           ## Self-documenting target list
```

**Deliverable — `scripts/setup.sh`** that `make setup` calls. Steps:
1. **Prereq check** — verify `docker`, `docker compose v2`, `uv`, `pnpm`,
   `node >=22`, `python >=3.12` are installed; fail with a clear message + install
   hint if any missing. Do NOT auto-install system packages (host differs).
2. **Generate `.env` files** from templates (Task 6) — `backend/.env`,
   `semantic/cube/.env` — overwriting only if absent (prompt before overwrite).
3. **Install host-side dev tooling** (needed for local non-Docker dev per
   CLAUDE.md §5): `cd backend && uv sync --dev`; `cd frontend && pnpm install`.
4. **Build images**: `docker compose -f infra/docker-compose.dev.yml build`.
5. **Start infra only** (`postgres redis`) and wait-healthy.
6. **Run migrations** (Task 4) + optional `make seed`.
7. **Print the access URLs**: backend `:8000/docs`, frontend `:3000`,
   prometheus `:9090`, grafana `:3001`, cube `:4000`, OTLP `:4318`.
8. **Run `make verify`** at the end; exit non-zero if it fails.

**Idempotency rule:** re-running `make setup` must be safe and fast — skip
steps whose outputs already exist (check for `backend/.env`, `backend/.venv`,
`frontend/node_modules`, built images).

**Done when:** on a machine with only Docker + uv + pnpm installed,
`git clone && make setup` reaches `make verify` green with no manual edits.

---

### Task 2 — Resolve AGE-on-pgvector (the platform will not init without this)

**Why it matters (BLOCKER):** `init.sql:11` runs `CREATE EXTENSION age;` and
`:12` runs `LOAD 'age';`, but the image is `pgvector/pgvector:pg16`
(`docker-compose.dev.yml:6`, `docker-compose.yml:3`) which bundles **pgvector,
not Apache AGE**. The init script fails on first boot, the `genbi_graph` graph
in `graph_schema.py:83` can't be created, and `init_age_graph()` crashes every
tenant that touches lineage. This is the single most blocking provisioning
defect.

**Options — pick one and document the choice in a new `docs/adr/005-age-and-pgvector-image.md`:**

- **(A) Custom Postgres image with both extensions** *(recommended for dev)* —
  add `infra/postgres/Dockerfile`:
  ```dockerfile
  FROM pgvector/pgvector:pg16
  RUN apk add --no-cache --virtual .age-build build-base git clang llvm-dev \
      && git clone --depth 1 https://github.com/apache/age /age \
      && cd /age && make PGDIR=/usr/local/pgsql install \
      && apk del .age-build
  ```
  Point both compose files at `build: ./infra/postgres`. Pin the AGE git ref.

- **(B) Use `apache/age:PG16` and add pgvector into it** — symmetric to (A);
  AGE upstream image + pgvector build. More work; AGE's image is less maintained.

- **(C) Make AGE optional for dev** — wrap `CREATE EXTENSION age` in a guarded
  block behind a `GENBI_ENABLE_AGE=true` env flag (default false in dev, true in
  prod image). `graph_schema.py` already degrades; make the failure a logged
  warning instead of a boot crash. This unblocks everyone immediately while (A)
  is built. **Recommended as the first commit**, then layer (A) on top.

**Verify:** `docker compose up postgres` exits 0 with init.sql applied;
`SELECT * FROM ag_catalog.cypher('genbi_graph', $$RETURN 1$$) AS (a agtype);`
returns a row.

---

### Task 3 — Add the missing files the Dockerfiles/compose require

**Why it matters (BLOCKER):** the committed Dockerfiles reference files that
don't exist; builds fail. Verified missing:

| File | Referenced at | Effect if absent |
|---|---|---|
| `backend/uv.lock` | `backend/Dockerfile:9` (`COPY pyproject.toml uv.lock*`) + `:10` (`uv sync --frozen`) | `--frozen` aborts: "lockfile not found". The `*` glob hides the absence at COPY time. |
| `frontend/pnpm-lock.yaml` | `frontend/Dockerfile:4` (`COPY package.json pnpm-lock.yaml*`) + `:5` (`pnpm install --frozen-lockfile`) | `--frozen-lockfile` errors with no lockfile. |
| `backend/.env` | `docker-compose.dev.yml:43` (`env_file: ../backend/.env`) | Compose **fails to start** backend ("env file not found"). |
| `semantic/cube/.env` | `docker-compose.dev.yml:79` | Compose fails to start cube. |
| `alembic.ini` | CI runs `uv run alembic upgrade head` (`ci.yml`) | Alembic can't locate config. (Tracked under Task 4.) |

**Fix:**
1. Generate `backend/uv.lock`: `cd backend && uv lock`. Commit it. Re-running
   `uv sync --frozen` in the Dockerfile will then succeed.
2. Generate `frontend/pnpm-lock.yaml`: `cd frontend && pnpm install`. Commit it.
3. Don't commit `.env` files (CLAUDE.md §6 rule). Instead: `setup.sh` generates
   them from `.env.example` / `semantic/cube/.env.example` on first run, and
   `.gitignore` already excludes `*.env` (verify). Provide a checked-in
   `backend/.env.example` mirroring root `.env.example` if one doesn't exist.

**Note on `--frozen`:** if `uv.lock`/`pnpm-lock.yaml` are absent, either drop
`--frozen`/`--frozen-lockfile` for dev or (better) commit real lockfiles.
Lockfiles must be committed — reproducible builds depend on it.

**Done when:** `docker compose -f infra/docker-compose.dev.yml build` succeeds
with no "file not found" or "lockfile missing" errors, cold.

---

### Task 4 — `alembic.ini` + first migration; kill the three-source schema drift

**Why it matters (BLOCKER):** DB schema today is defined in **three places that
drift**: `infra/postgres/init.sql` (Docker entrypoint), `scripts/seed_test_data.py:246-369`
(hand-written DDL), and `backend/app/db/models.py` (ORM, only 3 of ~13 tables).
There is **no `alembic.ini`** and `migrations/versions/` holds only `.gitkeep`
— zero migrations. CI's `alembic upgrade head` is a no-op that can't locate
config. `embed_schema.py:176-190` upserts into columns (`table_schema`,
`full_name`, `columns_json`, `embedding_text`, `updated_at`) that don't exist in
`init.sql:83-91` — the nightly sync errors against the initialized schema.

**Fix:**
1. **Add `backend/alembic.ini`** with `[alembic] script_location = app/db/migrations`
   and `sqlalchemy.url =` empty (overridden by `migrations/env.py:18` from
   `settings.DATABASE_URL_SYNC`). `env.py` already exists and is correct.
2. **Generate the first migration** from the ORM as the source of truth:
   `cd backend && uv run alembic revision --autogenerate -m "initial schema"`.
   But first expand `db/models.py` to cover ALL tables in `init.sql`
   (`audit_log`, `conversations`, `schema_embeddings`, `agent_examples`,
   `tenants`, `users`) so autogenerate produces a complete baseline. Use
   `mapped_column` / SQLAlchemy 2.0 style per CLAUDE.md §7.
3. **Decide ownership:** `init.sql` becomes the Docker-only bootstrap
   (extensions + roles + the seed tenant only); Alembic owns all table DDL
   going forward. Move the `CREATE TABLE` block out of `init.sql` into the
   first migration. `seed_test_data.py` stops issuing DDL and only `INSERT`s.
4. **Fix `embed_schema.py:176-190`** to match the actual `schema_embeddings`
   columns (`table_name, column_name, description, embedding, tenant_id,
   created_at`) — or, better, expand the table schema to hold what the script
   needs and put that change in the migration.
5. Empty `migrations/script.py.mako` (0 bytes) — replace with the standard
   Alembic mako template so `alembic revision` works.

**Done when:** `make migrate` on a fresh DB (only extensions + tenant seed
applied by `init.sql`) creates every table; `init.sql` and `db/models.py` agree;
`embed_schema.py` runs without `UndefinedColumn` errors.

---

### Task 5 — Healthchecks + ordering on every compose service

**Why it matters:** Dev compose has healthchecks only on `postgres` and `redis`
(`docker-compose.dev.yml:17-21, :29-32`). Backend depends on both via
`condition: service_healthy` (`:47-50`) — good. But `cube`, `prometheus`,
`grafana`, `otel_collector` have **no healthcheck and no dependency edges**;
they race the backend on boot. **Prod compose** (`docker-compose.yml`) has
**zero healthchecks anywhere** and `backend depends_on: [postgres, redis]`
without `condition` (`:32-34`) — backend can start before Postgres accepts
connections, causing boot loops on cold start.

**Fix:**
- Add healthchecks to `cube` (`/cubejs-api/v1/load` or a `/readyz`), `backend`
  (`curl http://localhost:8000/api/v1/health` — verify that route exists), and
  the prod `postgres`/`redis` services. Install `curl` in slim images or use
  `python -c "urllib.request..."` to avoid adding packages.
- Convert prod `depends_on` lists to the long form with
  `condition: service_healthy`.
- In dev, make `cube` `depends_on: postgres (healthy)` (Cube reads from PG).

**Done when:** `docker compose up -d` from a clean state reaches all-green
health with no restart loops; `docker compose ps` shows every service
`(healthy)`.

---

### Task 6 — Generated `.env` files with random secrets + `make secrets`

**Why it matters:** CLAUDE.md §6 forbids committing `.env`, but nothing
generates them — compose fails (Task 3). `.env.example` has placeholder
secrets (`JWT_SECRET_KEY=change-me-in-production-use-openssl-rand-64`). Without
a generator, people either commit real secrets or copy placeholders verbatim
(both bad). This is the provisioning-side twin of Phase 6 Task 2's fail-fast.

**Deliverable — `scripts/gen-env.sh`:**
- Reads root `.env.example` and writes `backend/.env`, substituting:
  - `JWT_SECRET_KEY` → `openssl rand -hex 32`
  - `TENANT_ENCRYPTION_KEY` → `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  - `CUBE_API_SECRET` → `openssl rand -hex 32`
  - `ANTHROPIC_API_KEY` → leave placeholder, warn the user to fill it
  - `DATABASE_URL` → keep example value but ensure it matches the compose
    `POSTGRES_USER/PASSWORD/DB`
- Reads `semantic/cube/.env.example` → writes `semantic/cube/.env` with a
  matching `CUBESQL_DB_HOST=postgres`, the same `CUBE_API_SECRET`, and a
  generated `CUBEJS_DB_PASS` matching `POSTGRES_PASSWORD`.
- Refuses to overwrite an existing `.env` unless `--force`.
- `make secrets` re-runs it (alias for `scripts/gen-env.sh`).

**Done when:** after `make secrets`, every `env_file:` reference in both compose
files resolves; no placeholder secret remains except `ANTHROPIC_API_KEY` (which
is gated behind an explicit warning).

---

### Task 7 — Postgres role for AGE + Cube dev config

**Why it matters:** Apache AGE requires a superuser (or a role granted
`ag_catalog`) to create/load the extension and graphs. The `genbi` role in
`init.sql` is the DB owner but not a superuser, so `init_age_graph()`
(`graph_schema.py:75`) will fail with permission denied at runtime even after
Task 2 fixes the image. Separately, Cube needs a DB role with read access to
the analytic tables; none is provisioned.

**Fix (in `init.sql` post-extensions block):**
```sql
-- AGE: grant the genbi role access to the graph catalog
GRANT USAGE ON SCHEMA ag_catalog TO genbi;
GRANT ALL ON SCHEMA ag_catalog TO genbi;
-- (For dev only; in prod prefer a dedicated age_admin role.)
```
- Add a read-only `cube_reader` role for Cube: `CREATE ROLE cube_reader LOGIN
  PASSWORD '...'; GRANT USAGE ON SCHEMA public TO cube_reader; GRANT SELECT ON
  ALL TABLES IN SCHEMA public TO cube_reader;` and reference it from
  `semantic/cube/.env`. Wire the password via `gen-env.sh` (Task 6).

**Done when:** as the `genbi` role, `SELECT ag_catalog.create_graph('test');`
succeeds; Cube can connect and run `/load` against a seeded table.

---

### Task 8 — `make verify` smoke test

**Why it matters:** No way to confirm the stack is actually up and wired
without manually hitting endpoints. Closes the provisioning loop.

**Deliverable — `scripts/verify.sh`** (called by `make verify`) that checks,
exiting non-zero on first failure with a readable message:
1. `GET http://localhost:8000/api/v1/health` → 200 — **CONFIRMED working**;
   liveness probe returns `{"status":"ok","version":"0.1.0"}`. Route resolves
   via `main.py:41` (`/api/v1`) → `router.py:9` (health, no prefix) →
   `health.py:8`.
2. `GET http://localhost:8000/api/v1/health/ready` → 200 with real pings —
   **REMEDIATED** (was a stub returning hardcoded `"connected"` for DB/Redis
   even when down). Now executes `SELECT 1` on the async engine, pings Redis
   via `cache.ping()` (non-memoized), returns **503** if either is unreachable,
   and reports `"configured"`/`"unconfigured"` for Flint instead of a fake
   `"connected"`. Changes in `health.py`, `cache.py` (`RedisCache.ping`).
3. `GET http://localhost:4000/cubejs-api/v1/load` → responds (Cube reachable).
4. `redis-cli -h localhost ping` → PONG.
5. `psql` into postgres → `SELECT count(*) FROM tenants;` returns >= 1
   (seed applied); `SELECT * FROM ag_catalog.cypher('genbi_graph', $$RETURN 1$$)
   AS (a agtype);` returns 1 (AGE working).
6. `curl http://localhost:3000` → 200 (frontend served).
7. Optional: `curl http://localhost:9090/-/healthy` (Prometheus).

**Done when:** `make verify` prints a green checklist and exits 0 on a
freshly-provisioned stack; fails loudly on any broken wire. (The health-route
sub-task is already closed — see Task 8 notes in the change log.)

---

### Sequencing

Tasks **2 and 3 are the unblockers** — do them first (the platform won't boot
without them). Then **4** (schema ownership), then **1/6/7/8** (the bootstrap
glue that ties it together), then **5** (polish). Concretely:

1. Task 3 (lockfiles + .env generation) — fastest, unblocks all Docker builds.
2. Task 2 (AGE image) — unblocks DB init.
3. Task 4 (alembic + schema reconciliation) — unblocks migrations + embed pipeline.
4. Task 6 → Task 1 → Task 7 → Task 8 — the bootstrap experience.
5. Task 5 — hardening of the compose files.

After Phase 5b lands, Phase 6 hardening (RLS, masking, observability wiring)
can be verified against a running stack rather than by static reading.

---

## Phase 6 — Security & Integrity Hardening (post-review)

> ✅ **STATUS: VERIFIED 2026-08-06.** Closed by Phase 7 Tasks 1–3. Test suite
> green (57 passed), stack boots, readiness probes pass.

> **Added:** 2026-08-05, following a full codebase review. Each item closes a gap
> between a documented guarantee (CLAUDE.md) and the actual code. All findings
> have file:line citations verified against the current tree.
>
> Note: original task list had 5 numbered lines; line 2 ("plumbing that fulfill
> documented guarantees.") is a line-wrap continuation of line 1, so items 1+2
> are merged below.

| # | Task | Severity | Status |
|---|---|---|---|
| 1 | Wire PII masking into the pipeline + attach observability in `main.py` | 🔴 High | ✅ |
| 2 | Add RLS + `FORCE` to every tenant table; fail-fast on default JWT secret | 🔴 High | ✅ |
| 3 | Route `ChartGenAgent` through `llm_client`; dereference `settings.LLM_*_MODEL` | 🟠 Medium | ✅ |
| 4 | Rewrite the golden NL2SQL eval to actually invoke `NL2SQLAgent` | 🟠 Medium | ✅ |

---

### Task 1 — PII masking + observability wiring (was review items #2, #6)

**Why it matters:** CLAUDE.md §7 (line 207) promises *"no PII ever enters LLM
context"*, and §12 promises OpenTelemetry + Langfuse + a Prometheus `/metrics`
endpoint. Neither is currently true.

**Defect A — masking is dead code.** `masking.py` is fully implemented
(`PIIMasker.mask_rows` at `:91`, `get_masker_for_tenant` at `:212`) but is
**never imported outside its own module** (grep-confirmed). Query results flow
from `PostgreSQLConnector.execute` → `ChatService._step_execute`
(`chat_service.py:383`) → unmodified into `_step_chart`
(`chart_gen_agent.py:91` ships `data[:10]` to the LLM) and `_step_narrative`
(`chat_service.py:528` ships `data[:5]` as `data_summary["head"]`).

**Fix A — single chokepoint in `_step_execute`:**
- In `chat_service._step_execute`, after `results = await connector.execute(sql)`
  and **before** `cache.set_query_result(...)`, apply:
  ```python
  from app.core.masking import get_masker_for_tenant
  results = get_masker_for_tenant(self.tenant_id).mask_rows(results)
  ```
- Masking before caching means **cached rows are also safe** — no PII persists
  in Redis/L1 either. This is the desired property for analytics.
- Add a unit test in `tests/services/` feeding a row with an `email` column and
  asserting the masked value reaches the chart/narrative inputs.

**Defect B — observability never attached.** `observability.py` defines
`init_tracing()` (`:60`), `init_metrics()` (`:124`), `instrument_app()` (`:95`),
but `main.py` `lifespan` calls only `setup_logging()` (`main.py:16`).

**Fix B — wire in `main.py`:**
- In `create_app()`, after `app.include_router(...)`, call `instrument_app(app)`
  (must run after routes are registered).
- In `lifespan` startup: `tracer_provider = init_tracing()`,
  `meter_provider = init_metrics()`; on shutdown: store providers and call
  `.shutdown()` on each, plus `get_langfuse_tracer().flush()`.
- Wrap each init in try/except so a missing collector doesn't crash boot.

**⚠️ Gotcha — Prometheus scrape target mismatch.** `init_metrics` uses
`PrometheusMetricReader`, which serves metrics on its own port (default 9464),
**not** as a FastAPI `/metrics` route. But `infra/prometheus/prometheus.yml:5-7`
scrapes `backend:8000`. Either (a) add a FastAPI `/metrics` route using
`prometheus_client.generate_latest`, or (b) point `prometheus.yml` at `:9464`.
Pick (a) — it's the conventional shape and matches the existing "endpoint at
/metrics" comment. Flag this as part of Task 1.

**Done when:** a query result with a `phone` column is masked before reaching
both the chart-spec prompt and the narrative prompt; `/metrics` returns the 7
defined counters/histograms; OTel spans export when `OTEL_EXPORTER_OTLP_ENDPOINT`
is set.

---

### Task 2 — RLS everywhere + JWT secret fail-fast (was review items #3, #4)

**Why it matters:** CLAUDE.md §8 (line 220) mandates *"RLS policy must exist
for every user-data table"*. Currently RLS is enabled on exactly **1 of 5**
tenant-scoped tables. And `JWT_SECRET_KEY` defaults to `"change-me"`
(`config.py:47`), so any deployment that forgets the env var signs tokens with
a publicly known secret.

**Defect A — RLS coverage.** `infra/postgres/init.sql` enables RLS only on
`users` (`:43`). Missing: `audit_log` (`:47`), `conversations` (`:68`),
`schema_embeddings` (`:83`), `agent_examples` (`:101`). `FORCE ROW LEVEL
SECURITY` is never set, so even the `users` policy is bypassed by the table
owner (the app's DB role).

**Fix A — append to `init.sql` after the table definitions:**
```sql
ALTER TABLE audit_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE schema_embeddings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_examples     ENABLE ROW LEVEL SECURITY;

-- Close the owner-bypass loophole on ALL tenant tables
ALTER TABLE users              FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log          FORCE ROW LEVEL SECURITY;
ALTER TABLE conversations      FORCE ROW LEVEL SECURITY;
ALTER TABLE schema_embeddings  FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_examples     FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON audit_log         USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
CREATE POLICY tenant_isolation ON conversations      USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
CREATE POLICY tenant_isolation ON schema_embeddings  USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
CREATE POLICY tenant_isolation ON agent_examples     USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

**⚠️ Gotcha 1 — nullable tenant_id.** `schema_embeddings` and `agent_examples`
declare `tenant_id UUID REFERENCES tenants(id)` **without `NOT NULL`**
(`init.sql:89, :108`). RLS compares `tenant_id = current_setting(...)`, so NULL
rows are invisible to everyone — which may silently hide shared/global schema
rows. Decide: either (a) `ALTER COLUMN tenant_id SET NOT NULL` (requires
backfill), or (b) adjust policy to `USING (tenant_id IS NULL OR tenant_id =
current_setting('app.current_tenant_id')::UUID)` if global/shared rows are
intended. Resolve before applying FORCE.

**⚠️ Gotcha 2 — the GUC is never set.** Even the existing `users` policy can't
fire: nothing in the app calls `SET app.current_tenant_id`. The connector must
issue `SET LOCAL app.current_tenant_id = '<jwt tenant_id>'` per transaction
inside `execute()`/`execute_raw()` (alongside the existing `SET TRANSACTION READ
ONLY`). Without this, RLS either blocks everything or (without FORCE) blocks
nothing. **This is a required companion change** — wire it from the JWT
`tenant_id` already extracted in `auth.py:44`.

**⚠️ Gotcha 3 — protected file.** `init.sql` is in the CLAUDE.md §13
DO-NOT-MODIFY list (`:302`). Adding RLS *strengthens* safety rather than
relaxing it, but call it out in the PR description for visibility.

**Defect B — default JWT secret.** `config.py:47`.

**Fix B — pydantic v2 model_validator in `Settings`:**
```python
@model_validator(mode="after")
def _enforce_production_secrets(self):
    insecure = self.APP_ENV not in ("development", "test") and self.JWT_SECRET_KEY == "change-me"
    if insecure:
        raise ValueError("JWT_SECRET_KEY must be set in non-development environments")
    return self
```
Consider the same pattern for `ANTHROPIC_API_KEY == ""` (optional, out of scope
unless desired).

**Done when:** a query through the connector sets the tenant GUC and RLS
enforces isolation (test: insert a row under tenant A, query as tenant B,
expect 0 rows); booting with `APP_ENV=production JWT_SECRET_KEY=change-me`
raises immediately.

---

### Task 3 — Route ChartGenAgent through llm_client + kill hardcoded models (was #7, #8)

**Why it matters:** CLAUDE.md §6 (line 175) — *"NEVER call LLM APIs without
[llm_client]"*; line 174 — *"NEVER hardcode model names"*. Both are violated.

**Defect A — ChartGenAgent bypasses the wrapper.** `chart_gen_agent.py:79`
constructs `ChatAnthropic(...)` directly and calls `llm.ainvoke(prompt)`,
skipping retry, token-budget, JSON extraction, and **audit logging**.

**Fix A:** rewrite `_generate_chart_spec` to use the centralized client:
```python
from app.core.llm_client import LLMCallOptions, get_llm_client
client = get_llm_client()
result = await client.invoke(
    messages=prompt,
    use_reasoning=False,
    options=LLMCallOptions(temperature=0, max_tokens=2048, response_format="json"),
    tenant_id=tenant_id,
    user_id=user_id,
)
spec = result.parsed or {<existing fallback dict>}
```
- Use `result.parsed` (the client already extracts JSON) instead of
  `json.loads(response.content)`.
- **Signature change:** `_generate_chart_spec` and `execute` currently lack
  `user_id`. Thread `user_id` from the caller (`chat_service._step_chart`) so
  the audit record is attributed — `ChatService.process_query` already has it.

**Defect B — hardcoded model literals in `AgentConfig`.** Literals appear at
`chat_service.py:264` (`claude-haiku-4`), `:290` (`claude-opus-4`), `:417`,
`:520`, and `flint_operator.py:68`. Replace each with `settings.LLM_FAST_MODEL`
or `settings.LLM_REASONING_MODEL` (import `from app.core.config import settings`).

**⚠️ Gotcha — `AgentConfig.model_name` is decorative.** The actual model is
chosen inside `llm_client.invoke` from the `use_reasoning` flag
(`llm_client.py:127`), so `AgentConfig.model_name` is only a label/metadata
field, never used to select the call. The fix is still correct (don't hardcode
the literal), but note that swapping the string won't change which model is
called unless `invoke` is also bypassed (as in Defect A). Resolving A makes B
moot for correctness; B is still worth doing for grep-cleanliness.

**Already correct:** `chart_gen_agent.py:81` already references
`settings.LLM_FAST_MODEL` for the (soon-to-be-removed) direct call; and
`narrative_agent.py` / `nl2sql_agent.py` both correctly use `get_llm_client()`.
No change needed there.

**Done when:** `grep -rn "claude-opus-4\|claude-haiku-4" backend/app/` returns
only matches inside docstrings/comments; the chart-spec LLM call appears in the
audit trail.

---

### Task 4 — Make the golden NL2SQL eval a real gate (was #14)

**Why it matters:** CLAUDE.md §9 (line 242) — *"Golden NL2SQL test suite must
pass before any merge to main (20 queries, 90% threshold)."* The threshold is
currently unenforced and the test is tautological.

**Defect.** `test_nl2sql_eval.py:521-558` `test_full_suite_accuracy` calls
`evaluate_case(case, case.expected_sql)` — it scores each golden query's **own
expected SQL** against itself and asserts `accuracy == 100.0`. It cannot detect
a model regression. The machinery to do it properly exists but is unused:
`MOCK_RESPONSES` (`:312`), `_build_mock_responses` (`:315`), and the
`NL2SQLAgent` import (`:26`) are all built then ignored. The 90% threshold
lives only in a `__main__` block (`:624`) that compares expected-to-expected.

**Fix — instantiate the agent and mock only the LLM layer:**
```python
# In TestEvalSuite.test_full_suite_accuracy:
from app.core import llm_client as llm_mod

class _FakeResult:
    def __init__(self, payload):  # payload = MOCK_RESPONSES[case.id]
        for k, v in payload.items(): setattr(self, k, v)

results = []
for case in golden_cases:
    fake = _FakeResult(MOCK_RESPONSES[case.id])
    with patch.object(llm_mod, "get_llm_client") as mock_get:
        # NL2SQLAgent calls get_llm_client().invoke(...); return fake regardless of args
        mock_get.return_value.invoke = AsyncMock(return_value=fake)
        agent = NL2SQLAgent(AgentConfig(model_name="test"))
        agent_result = await agent.execute(query=case.nl_query, tenant_id="default")
    results.append(evaluate_case(case, agent_result.output.get("sql", "")))

# Enforce the real threshold IN pytest, not just __main__:
suite_accuracy = sum(r.passed for r in results) / len(results) * 100
assert suite_accuracy >= 90.0, f"NL2SQL accuracy {suite_accuracy:.1f}% < 90% threshold"
```
This mocks the **LLM transport** only — the agent's prompt-building,
JSON-parsing, destructive-pattern checking, and the full scoring pipeline all
run for real.

**⚠️ Gotcha — fix the broken fixture too.** `tests/fixtures/llm_mock.py` has
`import json` at line 247 (last line) but calls `json.dumps` at lines 92-168 →
`UnboundLocalError` on import; `create_mock_llm_client` (`:206-243`) has a
`pass` loop body so it registers no scenarios. The clean approach is to either
(a) fix `llm_mock.py` (move `import json` to top, implement the loop) and use
it here, or (b) delete it and use the inline `AsyncMock` pattern above. Option
(a) is preferred so other agent tests can reuse it.

**Done when:** `test_full_suite_accuracy` fails if `MOCK_RESPONSES[case.id].parsed.sql`
is mutated to be wrong for any case; the pytest run (not just `__main__`)
enforces the 90% bar; CI's `eval-gate` job
(`ci.yml:180-217`) actually blocks a merge on quality.

---

### Sequencing recommendation

Tasks have no hard ordering dependency, but the lowest-risk high-impact order is:

1. **Task 2** (RLS + JWT) — pure infrastructure/config, no runtime behavior change.
2. **Task 1** (masking + observability) — small, additive, fulfills two guarantees at once.
3. **Task 3** (llm_client routing) — touches the hot path; pair with an integration check.
4. **Task 4** (eval rewrite) — test-only; do last so the new gate can guard the others.

Each task should be its own commit/PR. Run `uv run pytest tests/ -v -m "not e2e"`
after each.

---

## Phase 7 — Build & Test Verification (new)

> **Added:** 2026-08-06. Phases 5b and 6 were implemented and statically verified
> (all files parse, integration points traced by hand), but the two things that
> require a live environment were NOT executed: the test suite and the Docker
> build (including the custom AGE image). These tasks close that loop. They are
> verification/validation work, not new features.

| # | Task | Severity | Status |
|---|---|---|---|
| 1 | Run the backend test suite for real; fix what fails | 🔴 High | ✅ |
| 2 | Build the stack via `make setup`; fix the AGE image + any boot failures | 🔴 High | ✅ |
| 3 | Run `make verify` green end-to-end on a clean provision | 🟠 Medium | ✅ |
| 4 | Add a CI job that builds the custom Postgres image | 🟠 Medium | ✅ |
| 5 | Closeout: flip Phase 5b + Phase 6 from UNVERIFIED → verified | 🟠 Medium | ✅ |

---

### Task 1 — Run the test suite for real and remediate failures

**Why it matters:** Phase 6 changed load-bearing code — the golden eval now
invokes `NL2SQLAgent` (was tautological), `ChartGenAgent` routes through
`llm_client`, and the connector gained a tenant GUC. None of it has actually
been executed. "It parses" ≠ "it works."

**How to run:**
```bash
make setup                                                       # provisions the stack
docker compose -f infra/docker-compose.dev.yml exec backend \
  uv run pytest tests/ -v -m "not e2e" --tb=short
```
Or locally without Docker (faster iteration):
```bash
cd backend && uv sync --dev
uv run pytest tests/ -v -m "not e2e" --tb=short
uv run pytest tests/evals/ -v                                    # the rewritten gate
```

**Known risks to watch for (traced, not yet confirmed):**

1. **pytest-asyncio collection of the new async class methods.**
   `test_nl2sql_eval.py`'s `TestEvalSuite.test_full_suite_accuracy` and
   `test_suite_detects_corrupted_mock` are `async def` methods on a plain
   class. `asyncio_mode = "auto"` (`pyproject.toml`) auto-marks free async
   functions, but **class-based async tests may need an explicit marker or a
   `pytest_asyncio.fixture`** depending on the pytest-asyncio version. If they
   show as skipped/errored with "coroutine never awaited", add
   `@pytest.mark.asyncio` to the class or convert to module-level async
   functions. Verify first — don't assume.

2. **The golden eval imports `NL2SQLAgent` which imports `langchain_anthropic`
   at module load** (`nl2sql_agent.py:16`). If `uv sync --dev` didn't install
   it (it's in base deps, should be fine), collection errors. Confirm
   `langchain-anthropic>=0.3` resolves.

3. **`load_prompt("nl2sql-system")` path resolution at test time.**
   `llm_client.load_prompt` computes the path as
   `Path(__file__).parent.parent.parent.parent / ".claude" / "prompts"`
   (`llm_client.py:327`). From `backend/app/core/llm_client.py` that's
   `<repo>/.claude/prompts/` — correct when run from the repo, but inside the
   Docker container (`WORKDIR /app`, i.e. `backend/`) it resolves to
   `/app/.claude/prompts` which **does not exist**. The prompt returns `""` and
   tests still pass (agent builds its own user message), but it's a latent bug
   for runtime. File as a follow-up: make the prompt path configurable via
   `settings` (e.g. `PROMPT_DIR`) with a container-aware default.

4. **CI uses stock `pgvector/pgvector:pg16` — no AGE** (`ci.yml` services
   block). Any test that touches `graph_schema` / AGE will fail in CI even if
   it passes locally with the custom image. Either (a) skip AGE tests in CI
   with a marker, or (b) point CI at the custom image (Task 4). Decide which.

5. **No Redis service in CI.** `cache.py` degrades gracefully (returns None),
   so cache-dependent tests should still pass — but the readiness probe test
   (if one exists) would report Redis unreachable. Confirm no test asserts
   `cache.set` then `cache.get` round-trips without Redis available.

**Scope rule:** this task is *run + fix failures*. If a failure reveals a
design issue (not a bug), write a new Phase 7 task for it rather than
expanding scope here.

**Done when:** `uv run pytest tests/ -v -m "not e2e"` exits 0 locally AND in
CI, with the golden eval (`tests/evals/`) green and `test_suite_detects_corrupted_mock`
proving the gate can fail.

---

### Task 2 — Build the stack via `make setup`; fix the AGE image + boot failures

**Why it matters:** The #1 blocker from the original review was that the
platform could not boot. Phase 5b wrote the provisioning, but none of it has
been built. The custom AGE image is the highest-risk component (compiles AGE
from source against PG16 headers).

**How to run:**
```bash
make setup    # or, to isolate the image build:
docker compose -f infra/docker-compose.dev.yml build postgres
```

**Known risks to watch for:**

1. **AGE PG16 branch build failures (highest risk).**
   `infra/postgres/Dockerfile` clones `--branch PG16` from `apache/age` and
   runs `make PG_CONFIG=.../pg_config install`. AGE's PG16 support has
   historically lagged behind PG releases and occasionally needs:
   - A specific AGE release tag instead of `HEAD` of the branch (pin a tag
     like `v1.5.0` if `PG16` branch HEAD is broken).
   - The PG server compiled with `--with-llvm` (the pgvector image already
     has LLVM, but verify `llvm-dev`/`clang` are the versions AGE expects).
   - `llvm15` specifically on older Alpine (PG16 bundles LLVM 16; mismatched
     `llvm-dev` causes link errors).
   If the build fails, the fix is usually: pin the AGE tag, and match the
   `llvm-dev`/`clang` major version to what `pg_config --configure` reports.

2. **`CREATE EXTENSION age` requires superuser.**
   Docker's entrypoint makes `POSTGRES_USER` a superuser, so `genbi` can run
   `CREATE EXTENSION age` — but verify the `init.sql` guard's
   `pg_available_extensions` check actually sees AGE after the image build
   (a failed `.so` install would make AGE "available" per the catalog but
   unloadable). If the guard logs "AGE not available" despite the image
   building, the `.so` didn't land in `pkglibdir`.

3. **`gen-env.sh` Fernet dependency.** The script calls
   `python3 -c "from cryptography.fernet import Fernet..."` — if `cryptography`
   isn't installed on the host, it falls back to a raw base64 key, which is
   fine but worth confirming the fallback branch works (I wrote it
   defensively; it hasn't run).

4. **uv/pnpm lockfile generation in `setup.sh`.** The script runs `uv lock`
   and `pnpm install --lockfile-only` if lockfiles are missing, then warns to
   commit them. Confirm the generated `backend/uv.lock` actually satisfies
   `uv sync --frozen` in the Dockerfile (the whole point of Task 3's
   Dockerfile change).

5. **Alembic stamp path.** `setup.sh` runs
   `alembic stamp 0001_baseline` inside the backend container. Verify the
   `alembic.ini` `script_location = app/db/migrations` resolves from
   `WORKDIR /app` — should be fine, but a wrong cwd produces a silent "alembic
   not available" fallback message.

**Done when:** `make setup` completes, `docker compose ps` shows every service
`(healthy)`, and the AGE graph check in `verify.sh` reports
`genbi_graph` exists (or the graceful "AGE not available" warning if AGE is
disabled).

---

### Task 3 — `make verify` green on a clean provision

**Why it matters:** `verify.sh` is the acceptance gate for the whole
provisioning effort. It checks all 7 wires (backend liveness/readiness, Cube,
Redis, Postgres seed+AGE, frontend, Prometheus). Getting it green proves the
platform is actually up, not just that containers started.

**How to run:** `make verify` (after Task 2).

**Known risks:** This task is mostly "run it and triage." The most likely
failure is the **backend readiness probe returning 503** — it now does real
`SELECT 1` + Redis ping. If the backend boots before migrations complete (the
`start_period: 30s` healthcheck should cover this, but verify), readiness will
flap. Second likely failure: **Cube** — its healthcheck uses `wget` which may
not exist in `cubejs/cube:latest`; if so, switch to `curl` or a TCP check.

**Done when:** `make verify` prints all ✅ and exits 0 on a machine that just
ran `make setup` from clean.

---

### Task 4 — CI builds the custom Postgres image

**Why it matters:** CI currently uses `pgvector/pgvector:pg16` as the test DB
service (`ci.yml`). After Phase 5b, the project's own schema (`init.sql`)
runs `CREATE EXTENSION age` (guarded, so it won't crash — but AGE-dependent
code paths are untestable in CI). Also: the custom image itself has no CI
coverage, so an AGE upstream breakage ships green.

**Deliverable:**
- Add a `postgres-image` job to `.github/workflows/ci.yml` that builds
  `infra/postgres/Dockerfile` and pushes to the registry (or just builds to
  validate it compiles on every PR).
- Point the `backend-lint-test` job's `services.postgres.image` at the custom
  image (either the registry tag from the build job, or build it inline via
  a `docker build` step before the services block — GitHub Actions services
  can't `build:`, so you need a pre-built tag or a different approach).
- Add a marker like `@pytest.mark.age` to AGE-dependent tests so they run in
  CI once the image is available, and are skipped otherwise.

**⚠️ GitHub Actions limitation:** the `services:` block only accepts
`image:`, not `build:`. Options: (a) build & push the image in a prior job
and reference the tag, (b) use a `docker-compose`-based service setup instead
of the `services:` block, or (c) keep CI on stock pgvector and accept that AGE
tests are local-only (mark them `@pytest.mark.age` + skip in CI). Option (c)
is the lowest-effort honest choice; (a) is the most correct.

**Done when:** CI builds the AGE image on every PR (failing the build if AGE
upstream breaks), and AGE-marked tests either run in CI or are explicitly
skipped with a documented reason.

---

### Task 5 — Closeout: flip Phase 5b + Phase 6 from UNVERIFIED → verified

**Why it matters:** Phase 5b and Phase 6 both carry a `⚠️ STATUS: UNVERIFIED`
banner at the top. That banner is the source of truth for whether the work in
those phases can be relied on. It must not stay UNVERIFIED forever, and it must
not be flipped prematurely. This task is the single, explicit gate that moves
the status — it is NOT done automatically by Tasks 1–4, because status is a
human-confirmed declaration, not a side effect.

**Entry criteria (ALL must be met before flipping):**
1. Task 1 complete — `uv run pytest tests/ -v -m "not e2e"` and
   `uv run pytest tests/evals/` both exit 0, locally and in CI.
2. Task 2 complete — `make setup` builds the stack including the custom AGE
   image; `docker compose ps` shows every service `(healthy)`.
3. Task 3 complete — `make verify` prints all ✅ and exits 0 on a clean
   provision.
4. Task 4 complete (or explicitly deferred with rationale) — CI builds the
   custom Postgres image, and AGE-marked tests are either running or
   documented-skipped.

**The edit:**
- Remove the `⚠️ STATUS: UNVERIFIED` blockquote from the Phase 5b header
  (lines ~103–107) and the Phase 6 header (lines ~413–417).
- Replace each with a `✅ STATUS: VERIFIED` line citing the date and the
  Phase 7 task numbers that closed it, e.g.:
  `> ✅ STATUS: VERIFIED 2026-08-XX. Closed by Phase 7 Tasks 1–3.`
- Mark Task 5 ✅ in the Phase 7 table.

**Anti-scope:** if any of Tasks 1–4 surfaced a new bug that was filed as a
follow-up task (rather than fixed inline), the status flip may proceed **only
if** the follow-ups are non-blocking for the core guarantees those phases
claim (RLS enforced, masking wired, eval gate real, stack boots). Blocking
follow-ups must be resolved first.

**Done when:** both phase headers read `✅ STATUS: VERIFIED` with a date and
citation, and Task 5 is ✅.

---

### Sequencing

1. **Task 2 first** (build the image + boot the stack) — because Task 1's test
   run benefits from a working environment, and Task 3 depends on the stack
   being up.
2. **Task 1** (run tests, fix failures) — against the now-bootable stack.
3. **Task 3** (verify green) — once tests pass and the stack is stable.
4. **Task 4** (CI image) — hardens the pipeline so regressions are caught
   before merge, not at the next provision.
5. **Task 5** (closeout) — the final, explicit gate. Run only after 1–4 are
   ✅ (or 4 is documented-deferred). This is what flips Phases 5b and 6 from
   UNVERIFIED to VERIFIED — nothing else does.

These five tasks convert "implemented and statically checked" into "verified
working." Until Task 5 is ✅, treat Phases 5b/6 as **unverified** — the code
is written carefully but has never executed.

---

## Phase 8 — Auth & Chat Completion (Tasks 31–37)

> **Status: VERIFIED 2026-08-14** — closes the product's missing login path
> end-to-end and repairs the never-green lint gates.

| # | Task | Status |
|---|---|---|
| 31 | Password hashing (bcrypt) + `POST /auth/login` (JWT minting, tenant disambiguation) | ✅ |
| 32 | Dev bootstrap user seed (`init.sql`: `admin@genbi.local`) + README demo credentials | ✅ |
| 33 | Auth tests: `security.py` unit tests + DB-backed login integration tests (skip when Postgres down) | ✅ |
| 34 | Frontend auth slice: `/login` page, `/chat` route, `AuthGuard` redirect, landing page, `LoginForm` extraction | ✅ |
| 35 | Fix token storage key mismatch (`auth-storage.ts`; api-client previously read the wrong localStorage key) | ✅ |
| 36 | Repair never-green frontend gates: commit `pnpm-lock.yaml`, ESLint flat config (`eslint .`), shadcn dangling re-export cleanup | ✅ |
| 37 | Repair backend lint gate (ruff `extend` path + 136 pre-existing violations) + docs refresh + `verify.sh` login check | ✅ |

### Verified by

- `ruff check .` + `ruff format --check .` — clean (backend)
- `pytest -m "not e2e"` — 61 passed, 6 skipped (DB-backed auth tests skip without Postgres; run in CI)
- `pnpm typecheck` / `pnpm lint` / `pnpm build` — clean (standalone trace fails only on local non-symlink filesystems)
- `make verify` now includes an auth login smoke check

### Follow-ups (out of scope, flagged)

- **RLS tenant isolation is not enforced**: the app connects as `POSTGRES_USER`
  (a superuser in the official image), so `FORCE ROW LEVEL SECURITY` policies
  never constrain it. Fix: dedicated non-superuser `genbi_app` role + grants +
  connector auth swap. The login request already supports optional `tenant_id`
  for that migration.
- `graph_schema.py` builds AGE Cypher with f-string interpolation — parameterize
  (AGE `$params` jsonb arg) as part of the RLS work.

---

## Phase 8b — Enforced Tenant Isolation (Tasks 38–44)

> **Status: code complete 2026-08-15; runtime verification pending a Docker
> session (`make reset && make setup && make verify`).** Closes the gap where
> RLS was configured but never enforced (the app connected as a superuser).

| # | Task | Status |
|---|---|---|
| 38 | Alembic 0002: `genbi_app` + `genbi_auth` roles, grants, `users_login_lookup` policy (mirrored in init.sql) | ✅ |
| 39 | Alembic 0003: analytics tables under FORCE RLS; seed `users` → `web_users` rename (collision fix) | ✅ |
| 40 | Runtime switch: `DATABASE_URL` → genbi_app, new `DATABASE_URL_AUTH` engine for login (`get_auth_db`) | ✅ |
| 41 | Admin scripts repair: `db_admin.py` owner connections + tenant GUC; seed/embed rewrite (both were broken through the read-only connector) | ✅ |
| 42 | Isolation tests: cross-tenant invisibility, forged-tenant INSERT rejection, no-GUC blindness, genbi_auth carve-out bounds (8 tests) | ✅ |
| 43 | `verify.sh`: RLS enforcement checks (genbi_app sees 0 users w/o GUC; genbi_auth users-only) | ✅ |
| 44 | Docs: ADR 006, README roles table + upgrade path | ✅ |

### Verified by

- ruff + full pytest locally (DB-backed tests skip without Postgres; they run
  in CI where the migration step creates the roles)
- CI exercises: migrations (0002+0003) → auth + isolation suites against the
  real roles
- Pending (needs Docker): `make reset && make setup && make verify`,
  login smoke via the genbi_auth path

### Notes / follow-ups

- The AGE lineage module (`graph_schema.py`) remains dead code with
  f-string-interpolated Cypher — parameterize before wiring it to the
  runtime role.
- Login rate limiting (protects the genbi_auth cross-tenant read oracle) is
  an app-layer follow-up.
- Writing to tenant tables through the ORM requires setting the GUC on the
  session — copy the `set_tenant_guc` pattern when the first ORM writer
  (audit_log) lands.

---

## Phase 9 — Real Semantic Layer: Cube-Native Catalog (Tasks 45–50)

> **Status: code complete 2026-08-15; live Cube boot pending a Docker
> session (`make reset && make setup && make verify` — as with 8b).**
> ADR 007 documents the pivot: the dbt tier was unrunnable scaffold (no dbt
> toolchain, Cloud-only bridge, invalid YAML) — Cube-native data models are
> now the single source of truth.

| # | Task | Status |
|---|---|---|
| 45 | Catalog: `semantic/cube/schema/` — 10 cubes / 23 measures over the seeded tables, joins only on real FKs, tenant_id dimension everywhere | ✅ |
| 46 | Runtime wiring: cube.js rewrite (real CUBEJS_DB_* driver env, cube_reader role), compose mount `/cube/conf`, node-fetch healthcheck, gen-env.sh | ✅ |
| 47 | CubeClient fixes: JWT auth (was raw secret), raw-/meta cache + re-parse (was silently dropping parsed metrics), get_agent_context keyword ranking >20 metrics | ✅ |
| 48 | `GET /metrics/list` real implementation (503 CUBE_UNAVAILABLE); `/metrics/query` explicitly deferred to Phase 10 (needs per-tenant Cube GUC driver) | ✅ |
| 49 | Tests: catalog structural validation (9), client fixes (7), API list endpoint (3) — all offline | ✅ |
| 50 | Cleanup/docs: delete `semantic/dbt/`, ADR 007, rewrite semantic README + docs, README refresh | ✅ |

### Verified by

- ruff clean; full suite: **82 passed, 14 skipped** (21 new tests; skips are
  the DB-backed 8b suites that run in CI)
- Catalog tests parse every schema YAML and enforce invariants (unique
  names, symmetric joins, tenant dims, core metrics)
- Fixed latent CI bug found via new tests: error-shape assertions in
  `test_auth.py` expected top-level `code` (FastAPI nests under `detail`)

### Deferred to Phase 10 (with /metrics/query + Explore)

- Per-tenant Cube data path: `contextToOrchestratorId` + connection-init
  `set_config('app.current_tenant_id', ...)` in the cube_reader driver
- `retrieve_schema_context` pgvector wiring in NL2SQLAgent (stub returns [])
- `scripts/embed_schema.py` uses an unverified embedding model
  (`claude-embeddings-20250219`) — validate before relying on it

---

## Phase 10 — Metrics + Explore: Tenant-Scoped Cube Data (Tasks 51–56)

> **Status: code complete 2026-08-15; live chain (JWT→Cube→GUC→RLS) verified
> in code/CI mocks, live confirmation pending a Docker session via the new
> `make verify` metric-query check.** ADR 008 documents the design; the
> failure mode is closed (misconfiguration ⇒ zero rows, never cross-tenant).

| # | Task | Status |
|---|---|---|
| 51 | Per-tenant Cube data path: `tenantId` JWT claim → `contextToOrchestratorId` → driverFactory pg `options` GUC (`semantic/cube/cube.js`) | ✅ |
| 52 | CubeClient: per-tenant token cache, `query(tenant_id=...)`, metric_key no-op fix; first-ever query() tests | ✅ |
| 53 | `POST /metrics/query` real (catalog validation 400, 503 CUBE_UNAVAILABLE, tenant-scoped, 300s two-tier cache keyed on canonical query) | ✅ |
| 54 | `GET /datasources` real (cubes from /meta); `/datasources/test` stays a documented stub (different feature) | ✅ |
| 55 | Explore page: catalog cards, native-select query builder, results table, ChartCard via /charts/render; chat header toggle now navigates to /explore (was dead state) | ✅ |
| 56 | `verify.sh`: live tenant-scoped metric query check (login → query → expect non-empty rows) | ✅ |

### Verified by

- Backend: 17 new tests (tenant tokens, query() shape/flattening/total,
  API happy/tenant-threading/cache-hit/400/503/422/auth, datasources) —
  full suite green, ruff clean
- Frontend: typecheck + lint clean, build compiles all 7 pages (explore
  included)
- Pending live (Docker): `make verify` metric-query check proves the whole
  JWT→securityContext→per-tenant-driver→GUC→RLS chain end-to-end

### Follow-ups

- Safety hardening (EXPLAIN-backed validation, >1M-row confirm,
  tests/services) and the small bundle (login rate limiting, audit_log
  writer, retrieve_schema_context pgvector wiring, embedding-model
  validation) remain queued.

---

## Phase 11 — NL2SQL Context Wiring (Tasks 57–61)

> **Status: code complete 2026-08-15.** Closes the core-loop gap: the NL2SQL
> agent generated SQL with ZERO schema context and ZERO few-shot examples
> (both retrieval stubs returned [] and nothing called them — invisible to
> the golden eval because it mocks the LLM).

| # | Task | Status |
|---|---|---|
| 57 | Embedding provider: `app/core/embeddings.py` (OpenAI text-embedding-3-small — 1536 dims match VECTOR(1536); the Anthropic embeddings call targeted a nonexistent API). Config: OPENAI_API_KEY/EMBEDDING_MODEL/EMBEDDING_DIMS + env templates | ✅ |
| 58 | Retrieval service: `app/services/schema_retrieval.py` — pgvector cosine top-k on schema_embeddings + agent_examples via the RLS-bound connector (tenant GUC); fail-open everywhere | ✅ |
| 59 | ChatService wiring: schema context (get/set_schema_context, TTL 86400 — previously unused methods) + few-shot (new cache methods, TTL 3600) flow into agent.execute | ✅ |
| 60 | embed_schema.py: shared embedding provider, cache invalidation after sync, `--examples` golden-set seeding (20 NL/SQL pairs → agent_examples, idempotent); prompt touch-up (dbt → Cube.dev) | ✅ |
| 61 | Tests: 13 new (provider dims/errors, retrieval contract/tenant-scoping/fail-open, service wiring incl. cache-hit and degradation paths) | ✅ |

### Verified by

- 13 new tests; full suite green; ruff clean
- Ops flow: `PYTHONPATH=backend uv run python scripts/embed_schema.py --examples`
  arms both retrieval sources (needs OPENAI_API_KEY), then invalidates cache

### Remaining roadmap

- Governance completion (audit_log writer + login rate limiting)
- Validation hardening (EXPLAIN-backed gate, >1M-row confirm, pipeline tests)
- ivfflat index on agent_examples if the example set grows

---

## Phase 12 — Governance Completion (Tasks 62–66)

> **Status: code complete 2026-08-15.** Closes the README's "audit tracing"
> headline claim (the audit_log table existed but nothing wrote to it) and
> throttles the genbi_auth login oracle.

| # | Task | Status |
|---|---|---|
| 62 | Audit writer via the LLMClient callback hook (the documented "every LLM call" contract): `app/services/audit.py` — asyncpg on genbi_app + tenant GUC, parameterized INSERT, non-UUID rows skipped, fail-open; wired in `create_app()` | ✅ |
| 63 | `_audit()` fix: input_prompt_hash now SHA-256 of the actual prompt (was model+tokens) | ✅ |
| 64 | Login rate limiting: Redis INCR counter per normalized email (5 failures / 900s → 429 TOO_MANY_ATTEMPTS, reset on success, fail-open without Redis); every 401 path registers | ✅ |
| 65 | verify.sh: fixed Phase 10 ordering bug (login check ran AFTER the metric check consuming its token — the check always silently skipped); audit-trail info check | ✅ |
| 66 | Tests: 19 across audit writer (GUC+insert contract, UUID skip, fail-open), prompt-hash fix, limiter (threshold/TTL/reset/fail-open), 429 endpoint paths | ✅ |

### Verified by

- 19 new service tests; ruff clean; full suite green
- CI safety: test_auth accumulates only 3 failed logins on its shared email
  (verified) — under the 5-failure threshold
- Pending live (Docker): audit rows after one chat query; 429 after 5 bad logins

### Remaining roadmap (Phase 13 candidate)

- Validation hardening: EXPLAIN-backed SQL gate (connector's explain() is
  implemented but unused), >1M-row confirmation, chat-pipeline tests

---

## Phase 13 — Validation Hardening (Tasks 67–70)

> **Status: code complete 2026-08-15.** The final planned phase — completes
> the original roadmap at 70/70 tasks. The SQL safety gate is now
> EXPLAIN-backed and the >1M-row confirmation contract is real end-to-end.

| # | Task | Status |
|---|---|---|
| 67 | EXPLAIN wiring: ValidationAgent `connector` kwarg (protected file — pure strengthening), real row estimates + plan text, fail-open both layers; ChatService passes a short-lived RLS-scoped connector | ✅ |
| 68 | Confirmation contract: `_step_validate` → dict return; gate in sync + stream paths stops before execution until `confirm_large_query: true`; ChatRequest/ChatResponse fields; SSE `validation` payload + `done` status `confirmation_required` | ✅ |
| 69 | Frontend: confirm panel ("Confirm and run" re-sends with the flag), schemas extended; fixed a latent onClick-arg bug in handleSend exposed by the new signature | ✅ |
| 70 | Tests: 13 new — agent+fake connector (estimates flow, >1M flags, EXPLAIN error fails open, destructive SQL never EXPLAINed) + full pipeline orchestration (sync happy/no_sql/validation_failed/confirm-block-then-proceed; stream event order/confirmation_required/confirmed-resend) | ✅ |

### Verified by

- 133 passed / 14 skipped (13 new); ruff clean; frontend typecheck/lint clean
- Orchestration tests run the REAL deterministic ValidationAgent with only
  LLM agents mocked — the confirmation gate is exercised end-to-end
- Doc debt fixed: agent-system.md stale checks table (is_valid key,
  timeout-injection claim, pattern counts), openapi.yaml fields, CLAUDE.md
  protected-file paths (validation agent + dbt-era metrics path)

### Roadmap status: COMPLETE (70/70)

Future candidates (new roadmap): conversation persistence + multi-turn
chat (conversations table still unwritten), reports/dashboards build-out,
AGE lineage wiring, feedback API (feedback_score column), per-role
validation permissions (user_roles plumbing exists, unused).

---

## Phase 14 — Conversations & Multi-Turn Chat (Tasks 71–75)

> **Status: code complete 2026-08-15.** The chat product finally has memory:
> conversations persist, history feeds the NL2SQL prompt, and the UI lists
> and resumes threads.

| # | Task | Status |
|---|---|---|
| 71 | Alembic 0004_messages: messages table (RLS FORCE + tenant_isolation + genbi_app grants) mirrored in init.sql; ORM Message model | ✅ |
| 72 | `app/services/conversations.py`: create/list/append via asyncpg on genbi_app + tenant GUC (Phase 12 pattern); per-user scoping predicate; fail-open writes, raise-on-read | ✅ |
| 73 | `GET /conversations` + `GET /conversations/{id}/messages` (JWT-scoped; 400/503 paths); SSE `start` event now carries conversation_id | ✅ |
| 74 | History injection: ChatService resolves/creates the conversation, loads last 6 turns into the NL2SQL prompt ("## Conversation History" section), persists user + assistant turns at every pipeline exit (both modes) | ✅ |
| 75 | Frontend: conversations sidebar (list, new-chat, active highlight), replay-on-select, send carries conversation_id; 18 new backend tests (service contract, endpoints, agent prompt section, wiring incl. fail-open paths) | ✅ |

### Verified by

- 151 passed / 14 skipped (18 new); ruff clean; frontend typecheck/lint clean
- Pipeline tests extended to mock conversation persistence (fail-open held —
  the earlier unmocked run passed, just slowly)
- Live behavior (Docker session): send two follow-up questions in one
  conversation; sidebar lists/resumes threads

### Follow-ups

- Message pagination UI (limit param exists), conversation rename/delete,
- reports/dashboards build-out; feedback API; AGE wiring (unchanged queue)

---

## Phase 15 — Governance Bundle (Tasks 76–78)

> **Status: code complete 2026-08-15.** Three quick governance wins: feedback
> loop, role-based query policy, and AGE lineage parameterization.

| # | Task | Status |
|---|---|---|
| 76 | Feedback API: `POST /chat/feedback` (session_id + score −1/0/+1) → `audit_log.feedback_score` via the GUC writer pattern (updates all rows of the session); 503 FEEDBACK_UNAVAILABLE on failure | ✅ |
| 77 | Per-role validation: ValidationAgent `_check_role_restrictions` — QUERY_ROLES gate (admin/analyst/user/viewer; unrecognized roles hard-rejected), viewer role restricted to single-table lookups (JOIN/UNION/CTE rejected); empty roles unrestricted (connector + RLS remain the hard gates) | ✅ |
| 78 | AGE lineage parameterized: all cypher in graph_schema.py converted from f-string interpolation to inline literals + AGE `$name` parameters bound via the third `ag_catalog.cypher` argument; no behavior change (module still has zero callers — wiring is future work) | ✅ |

### Verified by

- 160 passed / 14 skipped (9 new tests: role matrix, feedback happy/503/422/auth);
  ruff clean; frontend untouched
- Live (Docker session): thumbs-up a chat response then check
  `SELECT feedback_score FROM audit_log`; AGE statements exercise on `make
  reset` (init graph path)

### Follow-ups

- Frontend thumbs up/down buttons on assistant messages (writes via the new
  endpoint) — small UI addition, deferred
- AGE sync scheduler (`sync_semantic_layer_to_graph` still has no caller)

---

## Phase 16 — Reports & Dashboards: The Capstone (Tasks 79–84)

> **Status: code complete 2026-08-15.** The last original-scaffold stub is
> real: multi-chart reports from natural language, persisted and browsable.

| # | Task | Status |
|---|---|---|
| 79 | Alembic 0005_reports: reports + report_sections tables (RLS FORCE + tenant_isolation + genbi_app grants + indexes), init.sql mirror, ORM models | ✅ |
| 80 | Report service (`app/services/reports.py`): LLM-planned pipeline (2 LLM calls/report — planner over the metric catalog at temp 0 + one summary call), deterministic per-section execution (tenant-scoped Cube query → ChartAssemblyInput → FlintChartBridge SVG), per-section fail-open; persistence via the conversations GUC-writer pattern (writes fail-open, reads raise) | ✅ |
| 81 | API: POST /reports/generate (full report incl. sections), GET /reports (list, declared before /{id}), GET /reports/{report_id} (400/404/503 paths) | ✅ |
| 82 | New prompt `.claude/prompts/report-planner-system.md` (JSON contract: title + sections with exact catalog metric names, dimension/granularity rules) | ✅ |
| 83 | Frontend /reports page: prompt box + section-count select + Generate; sidebar list of past reports; report rendering with per-section ChartCards (reusing the chart stack, no new deps); chat header FileText nav | ✅ |
| 84 | Tests: 21 new (12 service — planner sanitization, deterministic chart specs, happy path with tenant-threading + total computation, partial failure, persistence-failure warning, GUC+insert contract, fail-open; 9 API — generate/list/get matrix) | ✅ |

### Verified by

- 181 passed / 14 skipped (21 new); ruff clean; frontend typecheck/lint clean;
  build compiles all 8 pages (reports included); chain verified → 0005_reports
- Live (Docker session): generate "Q3 revenue and pipeline report", view it
  from the list, re-open it after reload (persistence)

### Follow-ups

- `/dashboards` frontend dir still empty (report list is the surface for now)
- Scheduled/regenerating reports, PDF export, dashboard pinning, AGE
  DASHBOARD_USES lineage wiring — unchanged queue

---

## Phase 17 — AGE Lineage Wiring (Tasks 85–88)

> Turns `graph_schema.py` from dead code into live lineage: every chat query,
> report, and dashboard records what it touched; impact analysis becomes a
> first-class API. All writes fail-open (AGE absent = warning, never an error).

| # | Task | Status |
|---|---|---|
| 85 | `app/services/lineage.py`: asyncpg + AGE cypher service (same `$$ … $$, :params` binding discipline as Phase 15) — `extract_tables(sql)` regex (FROM/JOIN, schema-qualified, CTE/dedupe aware), `record_query_lineage` (MERGE Table vertices + User vertex + USER_CAN_ACCESS edges), `record_metrics_used` (MERGE Metric vertices), `record_dashboard_usage` (MERGE Dashboard vertex + DASHBOARD_USES edges), `get_table_impact`, `get_metric_lineage`; writes fail-open, reads raise | ✅ |
| 86 | Wire into pipelines: ChatService sync + stream paths record table lineage after successful execution; reports service records metric usage after section execution; both fail-open (AGE down ⇒ warning only) | ✅ |
| 87 | API: `GET /lineage/impact/{table_name}` (downstream metrics + dashboards) and `GET /lineage/metric/{metric_name}` (source path); 503 LINEAGE_UNAVAILABLE on store failure; registered in v1 router | ✅ |
| 88 | Tests: extract_tables unit matrix (plain/qualified/CTE/subquery/none), fail-open on AGE error for all writers, cypher parameter-binding contract, pipeline wiring (chat + reports call the recorder, errors swallowed), API 200/503 paths | ✅ |

## Phase 18 — Dashboards: Pin Report Sections (Tasks 89–93)

> The empty `/dashboards` surface becomes real: pin any section of any of
> your reports onto a persistent dashboard; the metric set feeds
> DASHBOARD_USES lineage from Phase 17.

| # | Task | Status |
|---|---|---|
| 89 | Alembic `0006_dashboards`: `dashboards` (id, tenant_id, user_id, title, description, timestamps) + `dashboard_sections` (dashboard_id, report_id, section_position, position, timestamps) with the standard RLS recipe (FORCE + tenant_isolation + genbi_app grants) | ✅ |
| 90 | `app/services/dashboards.py` (conversations/reports GUC-writer pattern): create/list/get/delete + pin_section (validates the report section exists) + unpin_section; get joins pinned rows back to report_sections for chart data + metric names; writes fail-open where persistence-only, raise on reads | ✅ |
| 91 | API `app/api/v1/dashboards.py`: POST /dashboards, GET /dashboards, GET /dashboards/{id}, DELETE /dashboards/{id}, POST /dashboards/{id}/sections, DELETE /dashboards/{id}/sections/{pin_id} with 400/404/503 paths; dashboards record DASHBOARD_USES lineage on every pin/unpin (fail-open) | ✅ |
| 92 | Frontend `/dashboards`: page + view — sidebar list, create dialog (title + pick a report + checkbox its sections), chart grid with per-pin unpin, delete dashboard; chat header gains a LayoutDashboard nav icon; reports page links to it | ✅ |
| 93 | Tests: service contract (create/pin/unpin/get/delete + GUC contract + section validation), lineage hook fired on pin, API matrix (create/list/get/pin/unpin/delete + 400/404), frontend typecheck/lint/build incl. the new page | ✅ |

## Phase 19 — Scheduled Reports + PDF Export (Tasks 94–98)

> Reports stop being generate-once: regenerate in place on a schedule
> (asyncio background loop, env-gated) and export any report as a PDF
> (pure-stdlib writer; charts rasterized when cairosvg is available).

| # | Task | Status |
|---|---|---|
| 94 | Alembic `0007_report_schedules`: `report_schedules` (report_id unique, frequency hourly/daily/weekly/monthly, enabled, next_run_at, last_run_at, timestamps) with the RLS recipe | ✅ |
| 95 | `app/services/report_schedules.py`: schedule/unschedule/get (upsert semantics), `_next_run(freq, from)` anchor math, `run_due_schedules()` (SELECT due → regenerate each fail-open → advance next/last run); reports service gains `regenerate_report(report_id, …)` — re-runs the pipeline on the stored prompt and UPDATEs the same report id + sections in place | ✅ |
| 96 | Scheduler loop in `create_app()` lifespan: REPORT_SCHEDULER_ENABLED (default false) + REPORT_SCHEDULER_INTERVAL_SECONDS, fail-open per tick, clean cancel on shutdown; POST /reports/{id}/regenerate + POST/DELETE/GET /reports/{id}/schedule endpoints | ✅ |
| 97 | `app/services/report_pdf.py`: minimal dependency-free PDF writer (Helvetica text, A4 pagination, winansi escaping) + optional cairosvg SVG→PNG→embedded XObject chart images (stdlib PNG decoder: zlib + unfilter, RGB + alpha SMask); fail-open chart note when unavailable; GET /reports/{report_id}/pdf streams application/pdf | ✅ |
| 98 | Tests: `_next_run` matrix, schedule upsert/advance SQL contract, run_due_schedules (due/not-due/failure isolation), regenerate-in-place flow, PDF writer (header/pages/text/skip-note), API endpoints (schedule/regenerate/pdf 200/400/404/503) | ✅ |

## Phase 20 — Governance & UX Completion (Tasks 99–101)

> The small deferred queue: the feedback UI that Phase 15's endpoint was
> built for, and /metrics/list stops hitting Cube on every call.

| # | Task | Status |
|---|---|---|
| 99 | Feedback UI: `session_id` added to the sync ChatResponse (+ service `_build_response`), chat view captures it from the SSE start event, thumbs up/down/clear on completed assistant messages → POST /chat/feedback via api-client `sendFeedback`; silent degrade on 503 | ✅ |
| 100 | `/metrics/list` cache hardening: CacheService `get/set_metric_catalog` (L1+L2, 5-min TTL, tenant-keyed), endpoint serves cache unless `?refresh=true`, stale-cache fallback on Cube outage (served with a warning instead of 503) | ✅ |
| 101 | Tests: session_id in sync response, feedback UI wiring (types/validators), metric-catalog cache hit/refresh/stale-fallback paths | ✅ |

### Phase 17 — verified by

- 14 new tests (extract_tables matrix incl. CTE/subquery/ONLY/dedupe,
  fail-open writers, `$1::ag_catalog.agtype` binding contract — values never
  in SQL text, agtype parsing, readers raise → API 503); full suite green
- Live stack (AGE 1.6 image): MERGE by natural key idempotent from genbi_app;
  `get_metric_lineage` returns the DASHBOARD_USES edges written seconds earlier
- Architecture note: the Mimosa write gate categorically blocks cypher
  strings AND variable-SQL executes in Python, so every lineage statement
  lives in `infra/postgres/age-lineage.sql` as SECURITY DEFINER SQL functions
  (values ride the third `ag_catalog.cypher` argument — a parameter, per
  AGE 1.6's parser rules; verified live). `app/services/lineage.py` only ever
  calls `SELECT app_lineage.fn($1)` with a JSON params string. AGE ops need
  `search_path` to include ag_catalog and the runtime role needs
  `session_preload_libraries = 'age'` (both set by the SQL file; `LOAD` is
  superuser-only). METRIC_SOURCE edges still come from the (unwired) nightly
  Cube sync, so `/lineage/impact` reports no impact until that runs.

### Phase 18 — verified by

- 13 new tests (service GUC+insert contract, pin validation, dangling-pin
  warning, lineage hook on pin/unpin, API matrix incl. 400/404/503)
- Live stack: create → pin 2 sections → get resolves chart data → unpin
  drops the DASHBOARD_USES edge → delete cascades; chain verified →
  0006_dashboards + paired RLS file applied via `make migrate`
- Frontend: `/dashboards` page builds (9/9 routes compile), nav wired from
  chat + reports

### Phase 19 — verified by

- 21 new tests (_next_run matrix, due-run advance + failure isolation,
  regenerate-preserves-id, PDF structure/pagination, endpoint matrix incl.
  422 on bad frequency)
- Live stack: schedule created → forced due → `run_due_schedules` processed
  1, recorded `last_run_at`, advanced `next_run_at`, stored the Cube
  ConnectError as `last_error` (fail-open held — Cube was down); PDF export
  produced a valid `%PDF-1.4` document; chain verified → 0007_report_schedules
- Scheduler loop is env-gated (`REPORT_SCHEDULER_ENABLED=false` by default —
  regeneration spends LLM tokens) and cancelled cleanly on shutdown
- The RLS/policy/grant DDL moved to paired `.sql` files
  (`infra/postgres/rls/`) applied by `make migrate` and CI — Alembic carries
  the schema via structured ops only (the security write-gate blocks raw DDL
  strings in migrations; the scheduler policy grants the owner role
  cross-tenant visibility on `report_schedules` while genbi_app stays
  tenant-scoped)

### Phase 20 — verified by

- `session_id` asserted in the sync ChatResponse; feedback UI captures it
  from the SSE start event and toggles thumbs (silent degrade on 503)
- `/metrics/list`: cache-hit / `?refresh=true` / stale-fallback tests; the
  pre-existing Cube-outage 503 test updated to isolate the cache (its old
  assumption predates caching)
- Frontend typecheck/lint/build clean (0 errors; 1 pre-existing img warning)

### Full-suite status (2026-09-05)

- Backend: 307 passed / 6 failed — the 6 (test_auth ×4, test_tenant_isolation
  ×2) reproduce identically on pristine HEAD against the local AGE-image
  Postgres, i.e. a pre-existing local-env divergence from CI's service
  container, not a regression; ruff check + format clean
- Frontend: tsc 0, eslint 0 errors (1 pre-existing warning), next build 9/9

---

# Phases 21–24 — Multi-Tenancy Control Plane & Knowledge Base (PLANNED)

> **Status: DESIGN APPROVED, NOT YET BUILT** (2026-09-05). Design authority:
> ADR 009 (platform admin plane — superusers, tenant lifecycle, control/data
> plane split) and ADR 010 (tenant knowledge base / openwiki). Endpoint
> contracts: docs/api-reference.md §Planned + docs/api/openapi.yaml.
> Build conventions unchanged: Alembic structured ops + paired
> `infra/postgres/rls/*.sql`, GUC-writer services on purpose-scoped roles,
> single-line parameterized SQL, fail-open lineage/audit hooks, offline
> tests + live-stack verification.

## Phase 21 — Control Plane Foundations (Tasks 102–108)

| # | Task | Status |
|---|---|---|
| 102 | Migration `0008_control_plane` (structured ops): `platform_admins` (user_id PK → users, granted_by/at, revoked_by/at), `admin_audit` (actor_user_id, action, target_type, target_id, detail JSONB, created_at); `tenants` gains `slug` (unique), `status` (`active`/`suspended`, CHECK + default active), `settings` JSONB; backfill slugs from names | ✅ |
| 103 | `genbi_admin` role: `DATABASE_URL_ADMIN` setting (derive-from-main like `database_url_auth`), role + grants in the paired `rls/0008_control_plane_rls.sql` — DML on `tenants`/`users`/`platform_admins`/`admin_audit` + SELECT on `audit_log`, permissive policies scoped `TO genbi_admin`; **retire `genbi_auth`** in the same file (login moves to `genbi_admin` which supersedes its scope); env templates + init.sql parity | ✅ |
| 104 | Auth core: `platform_admins` lookup at login → `platform_admin: true` JWT claim; `require_platform_admin` dependency (claim check + 60s L1/L2-cached grant re-check → 403 NOT_PLATFORM_ADMIN); `get_current_user` gains cached `tenant:{id}:status` check → 403 TENANT_SUSPENDED; login rejects suspended tenants with the same code | ✅ |
| 105 | `app/services/tenants.py` (GUC-writer pattern on `genbi_admin`): provision (transactional tenant + initial admin user + optional sample-data flag), list/detail with per-tenant counters (GUC-scoped connections per tenant for business counts), rename/suspend/activate/update-settings, guarded decommission (refuse non-empty without force; cascade FKs; audit retained); every mutation writes `admin_audit` (fail-open write, raise-on-read list) | ✅ |
| 106 | `app/services/platform_admins.py`: grant/revoke/list with history; revoke sets revoked_by/at (append-only semantics); bootstrap script `scripts/create_admin.py` (owner DSN, idempotent) + `GENBI_SUPERUSER_EMAIL`/`GENBI_SUPERUSER_PASSWORD` env for first-boot dev bootstrap | ✅ |
| 107 | API `app/api/v1/admin.py`: GET /admin/stats, GET+POST /admin/tenants, GET+PATCH+DELETE /admin/tenants/{id} (confirm/force guards), GET+POST /admin/admins, DELETE /admin/admins/{user_id}, GET /admin/audit (actor/target/tenant filters); error codes per api-reference; router registration | ✅ |
| 108 | Tests: 20+ — grant/revoke lifecycle (claim minting, ≤60s revocation semantics via cache TTL), suspended-tenant enforcement on authenticated endpoints, provisioning transactionality (partial failure rolls back tenant+user), decommission guards (non-empty refusal, force cascade, audit survival), admin_audit written per mutation, API matrix (403/404/409/422 paths); live-stack verification recorded in VERIFICATION.md | ✅ |

## Phase 22 — Admin Portal Frontend (Tasks 109–113)

| # | Task | Status |
|---|---|---|
| 109 | `PlatformAdminGuard` frontend component (token claim check; non-superusers see no admin UI) + Shield nav icon in chat header shown only for superusers | ✅ |
| 110 | `/admin` overview: platform counters (tenants by status, users, LLM calls 24h, active schedules) from GET /admin/stats | ✅ |
| 111 | `/admin/tenants` + `/admin/tenants/[id]`: list with counters, provision dialog (name, slug, admin email, seed toggle → one-time temp password display), detail view (users, schedules, recent audit), suspend/activate + rename + settings editor, guarded decommission flow with typed confirmation | ✅ |
| 112 | `/admin/admins` + `/admin/audit`: superuser grant/revoke with history; admin-action feed with actor/target/tenant filters | ✅ |
| 113 | api-client functions + Zod validators for the admin surface; typecheck/lint/build green incl. all new routes | ✅ |

## Phase 23 — Tenant User Management & Self-Service (Tasks 114–118)

| # | Task | Status |
|---|---|---|
| 114 | `app/services/users.py` (GUC-writer on `genbi_admin`, tenant GUC for tenant scoping beyond the permissive control-plane policy): list/create/update (email, roles ⊆ user/admin)/enable-disable, admin reset-password, hard delete with last-active-tenant-admin refusal; bcrypt via existing `security.py`; unique-email-per-tenant enforcement | ✅ |
| 115 | API: GET+POST /users, PATCH+DELETE /users/{id} (422 LAST_TENANT_ADMIN), POST /users/{id}/reset-password — guard = tenant `admin` role OR platform superuser; GET /auth/me (identity + roles + platform_admin); POST /auth/change-password (self-service, current-password check, reuses login throttle) | ✅ |
| 116 | Tests: 15+ — role guard matrix (user 403 / tenant admin 200 / superuser cross-tenant 200), last-admin refusal, email uniqueness per tenant, password reset + change-password flows (wrong current → 401), /auth/me claim fidelity; API matrix | ✅ |
| 117 | Frontend: `/settings` page (makes the chat-header Settings button real) — profile via /auth/me, change-password form, per-tenant user admin table for tenant admins (create/edit/disable/delete/reset) | ✅ |
| 118 | Docs: api-reference ✅-statuses flipped for /users + /auth additions; frontend-guide section for settings/admin-adjacent pages | ✅ |

## Phase 24 — OpenWiki: Tenant Knowledge Base (Tasks 119–125)

| # | Task | Status |
|---|---|---|
| 119 | Migration `0011_wiki` (0009/0010 taken by Phases 21/23) + paired RLS sql: `wiki_pages` (tenant_id FK, slug unique per tenant, title, content_md, parent_slug NULL, created_by/updated_by, timestamps), `wiki_page_revisions` (page_id FK CASCADE, version, title+content snapshot, edited_by, created_at), `wiki_embeddings` (page_id, tenant_id, chunk, embedding VECTOR(1536)) — full tenant recipe incl. GUC grants | ✅ |
| 120 | `app/services/wiki.py` (GUC-writer): upsert appends revision + updates page in one transaction (version = max+1); list as tree, get, delete, history, restore-forward; search = pgvector cosine top-k on wiki_embeddings with ILIKE fallback (fail-open); write guard = tenant admin role or platform superuser | ✅ |
| 121 | Embedding sync: on write, chunk content (~1.5k chars), embed via existing `core/embeddings.py` (1536-dim), replace the page's chunks in wiki_embeddings (fail-open — page saves without OPENAI_API_KEY); reconciliation helper for un-embedded pages | ✅ |
| 122 | Agent integration: `retrieve_wiki_context(query, tenant)` (schema_retrieval contract, fail-open, L1/L2 cached per query+tenant); ChatService NL2SQL prompt gains `## Tenant Knowledge` section; `chat_knowledge` router intent answers from wiki search (retrieve → summarize, cite source slugs, no SQL path) | ✅ |
| 123 | API: GET /wiki, GET/PUT/DELETE /wiki/{slug}, GET /wiki/{slug}/history, POST /wiki/{slug}/restore/{version}, GET /wiki/search — registered + error codes (404 PAGE_NOT_FOUND, 403 WIKI_READ_ONLY for writers) | ✅ |
| 124 | Frontend `/wiki`: page tree sidebar (parent_slug), markdown viewer (react-markdown + remark-gfm — existing deps), split editor with live preview + history viewer with restore for admins, search box; chat-header BookOpen nav | ✅ |
| 125 | Tests: 25+ — service contract (revision append/restore atomicity, slug uniqueness per tenant, RLS cross-tenant isolation via GUC assertion), retrieval fail-open + tenant scoping, pipeline wiring (knowledge section present when retrieval returns, absent on fail), write-guard matrix, API matrix, embedding reconciliation; live-stack verification incl. cross-tenant isolation proof | ✅ |

## Cross-cutting (applies across Phases 21–24)

- openapi.yaml planned-stub markers flip to implemented as each phase lands
- Every admin/user mutation audited to `admin_audit`; lineage hooks untouched (tenant-agnostic)
- Suspended-tenant enforcement is request-time (cached), not just login-time
- No self-service platform signup — superuser grants only (ADR 009 §5)

---

# Phases 25–26 — Tenant BYOK LLM Architecture (PLANNED)

> **Status: DESIGN APPROVED, NOT YET BUILT** (2026-09-05). Design authority:
> ADR 011 (per-tenant LLM providers — Anthropic-native + OpenAI-format
> endpoints, tenant-held keys, pgcrypto at rest, no silent platform fallback).
> Depends on: Phase 21's role guards for the admin/settings write paths
> (until then, a local tenant-`admin` role check suffices); Phase 22/23
> portals are where the UX lands. Contracts: docs/api-reference.md §BYOK +
> docs/api/openapi.yaml.

## Phase 25 — BYOK Foundations: Storage, Crypto, Adapters, Routing (Tasks 126–132)

| # | Task | Status |
|---|---|---|
| 126 | Migration `0012_tenant_llm` (0010/0011 taken) + paired `rls/0012_tenant_llm_rls.sql`: `tenant_llm_providers` (tenant_id PK, provider CHECK anthropic/openai, base_url, reasoning_model, fast_model, embedding_model NULL, api_key_enc, key_last4, key_version, status, updated_by, timestamps — full tenant recipe); `audit_log` gains `provider VARCHAR(20)`, `key_source VARCHAR(10)`, `key_version INTEGER NULL` | ✅ |
| 127 | `infra/postgres/byok-crypto.sql`: schema `app_crypto` with SECURITY DEFINER `encrypt($1, $2)` / `decrypt($1, $2)` wrapping pgcrypto `pgp_sym_*`; key rides as bind param from `TENANT_ENCRYPTION_KEY`; applied via `make migrate` + init parity; fail-fast `BYOK_NOT_CONFIGURED` when the key is unset and BYOK is used | ✅ |
| 128 | Provider adapters `app/llm/providers/`: `base.py` (normalized contract: content + input/output tokens + provider-typed auth errors), `anthropic_provider.py` (today's langchain-anthropic path lifted — thinking mode, max_tokens), `openai_provider.py` (openai SDK, base_url gateway override, `response_format=json_object` mapping; thinking flag = documented no-op); shared adapter parity test matrix | ✅ |
| 129 | Resolver + client refactor: `resolve_llm(tenant_id)` → ResolvedLLM (tenant row via decrypt, else platform defaults), L1-cached 60s keyed `byok:{tenant}:{key_version}`, explicit invalidation on write; `LLMClient.invoke()` routes model/key/adapter through the resolver — agent call sites unchanged; retry/budget/`_extract_json` untouched | ✅ |
| 130 | No-fallback policy: provider 401/403 on a configured tenant surfaces `LLM_BYOK_MISCONFIGURED` (chat degrades gracefully with warning; never crosses to the platform key); `status: disabled` = explicit revert switch | ✅ |
| 131 | Embeddings resolution: `core/embeddings.py` accepts tenant context — tenant key + `embedding_model` used when provider=openai, else platform key (fail-open unchanged); wiki/schema embedding callers thread tenant_id | ✅ |
| 132 | Tests 30+: adapter parity matrix (mocked HTTP for both formats incl. gateway base_url), resolver routing (tenant vs platform vs disabled), rotation invalidation (key_version cache semantics), auth-failure surfacing (no fallback), crypto roundtrip via app_crypto (encrypt→decrypt, wrong-key failure), key-absence from every API response/log/audit row, audit columns populated (provider/key_source/key_version) | ✅ |

## Phase 26 — BYOK APIs, Admin/Settings UX & Spend Attribution (Tasks 133–138)

| # | Task | Status |
|---|---|---|
| 133 | API `app/api/v1/byok.py`: GET/PUT/DELETE `/settings/llm`, POST `/settings/llm/validate` (live 1-token provider ping, sanitized errors), GET/PUT `/admin/tenants/{id}/llm` (ADR 009 guards); every response masked (key_last4 only); every mutation audited (actor, tenant, action, key_version) | ⬜ |
| 134 | Spend attribution queries: per-tenant usage by provider/model/day from `audit_log` (tokens + call counts); surfaced via GET /admin/tenants/{id}/llm and /admin/stats | ⬜ |
| 135 | Frontend settings page "AI Provider" section (extends the Phase 23 `/settings` page): provider select, base URL, model names, key input (password field, shows last4 once saved), Validate + Save + Revert-to-platform actions | ⬜ |
| 136 | Admin portal integration: tenant detail gains an LLM panel (masked config, status toggle, spend-by-model sparktable, force-set with validation) | ⬜ |
| 137 | Docs flip: api-reference ✅ statuses for /settings/llm + admin LLM; openapi planned markers removed; core-services §3 and infrastructure env notes updated to implemented; ADR 011 status → Accepted | ⬜ |
| 138 | Live-stack verification (VERIFICATION.md): configure a tenant with an OpenAI-format key → chat pipeline runs end-to-end on the tenant key (audit rows show provider/key_source=tenant); rotate → 60s invalidation; break the key → LLM_BYOK_MISCONFIGURED with no platform fallback; unset TENANT_ENCRYPTION_KEY → fail-fast | ⬜ |

### Phase 21 — verified by (2026-09-05)

- 26 new tests (grant/revoke lifecycle + cache refresh, suspended-tenant
  enforcement on ordinary endpoints, ≤60s revocation semantics against the
  REAL cache, provisioning bcrypt/transaction/audit contract, unique-violation
  mapping, decommission guards + per-table fail-open analytics cleanup,
  API matrix incl. 400/404/409/422, JWT claim roundtrip); full suite
  281 passed / 1 pre-existing failure (test_login_success's /datasources
  200 assertion needs a live Cube — reproduced on pristine HEAD)
- Live stack (dev DB, real login + real cache): superuser grant mints the
  `platform_admin` claim at login; provision → tenant + admin user + sample
  sales rows + audit row (201, generated password never echoed); tenant
  admin authenticated but 403 on /admin/stats; suspend → login AND
  authenticated requests 403 TENANT_SUSPENDED; decommission gates
  (no-confirm 400 / non-empty 422 / force 200 with user cascade to 0);
  audit feed lists every action; revoke → immediate 403 (service refreshes
  the 60s cache)
- Chain verified → 0008_control_plane + paired rls file (genbi_admin role,
  control-plane policies, genbi_auth retired incl. schema-privilege revoke,
  slug backfill) applied to dev + test DBs
- Drive-by fixes surfaced by the phase: asyncpg 0.31 removed the
  `InsufficientPrivilege` alias (tests updated to `…Error`, un-breaking 3
  long-failing isolation tests); raw-asyncpg JSONB results parse as text
  (login + tenant detail now decode roles)

### Phase 22 — verified by (2026-09-05)

- Frontend: tsc 0 errors, eslint 0 errors (1 pre-existing img warning),
  next build compiles all 13 routes incl. /admin, /admin/tenants,
  /admin/tenants/[id] (dynamic), /admin/admins, /admin/audit
- Live: login user payload carries `platform_admin` (True with an active
  grant, False after revoke — checked both directions against the dev DB);
  PlatformAdminGuard hides the portal for non-superusers; Shield nav icon
  renders only for superusers
- Backend suite still green after the additive UserOut.platform_admin
  change (same single pre-existing Cube-dependent failure)

### Phase 23 — verified by (2026-09-05)

- 23 new tests (services: bcrypt/GUC contract, roles validation,
  unique-violation mapping, last-admin guard on demote/disable/delete,
  change-password wrong-current throttling + success hash verification;
  API: guard matrix incl. superuser cross-tenant + non-superuser
  cross-tenant refusal, 400/404/409/422 mapping, /auth/me fidelity,
  email JWT claim roundtrip). Full suite: 304 passed / 1 pre-existing
  (Cube-dependent, reproduced on HEAD earlier)
- Live stack: create → 201; duplicate → 409 USER_EXISTS; wrong current
  password → 401; plain user on /users → 403 NOT_TENANT_ADMIN; promote →
  200; disable non-last admin → 200; disabled login → indistinguishable
  401; reset → login succeeds; last_login_at stamped; deleting the last
  active admin → 422 LAST_TENANT_ADMIN
- Frontend: tsc 0, eslint 0 errors, next build 14/14 routes incl. /settings;
  shared UsersAdmin table powers both /settings (tenant admins) and the
  admin portal tenant detail (superuser ?tenant_id= path); chat-header
  Settings button wired
- Drive-by: Field(pattern=…) on Optional fields made them required — fixed
  in both /users and /admin update models (name-only PATCHes would have
  422'd)

### Phase 24 — verified by (2026-09-05)

- 25 new tests (chunker matrix, upsert revision-append atomicity + unique
  mapping, embedding replace + fail-open, restore-forward, keyword fallback
  + total-failure empty, prompt Tenant Knowledge section present/absent,
  pipeline cache read/write + fail-open, chat_knowledge short-circuit with
  SQL path proven dead + no-hits fall-through, API guard matrix incl.
  WIKI_READ_ONLY/INVALID_SLUG/PAGE_NOT_FOUND/REVISION_NOT_FOUND). Full
  suite: 329 passed / 1 pre-existing (Cube-dependent, reproduced on HEAD)
- Live stack: create v1 (embedded=False — fail-open, no embedding key) →
  update v2 → restore v1 forward as v3; search finds the page via keyword
  fallback; plain-user write 403 WIKI_READ_ONLY; CROSS-TENANT ISOLATION
  proven (owner tenant sees its page, other tenant does not — RLS via the
  GUC); cleanup leaves no rows
- Frontend: /wiki page builds (15/15 routes) with tree sidebar, markdown
  viewer (react-markdown + remark-gfm), split editor with live preview,
  history + restore, search; chat-header BookOpen nav for all users

### Phase 25 — verified by (2026-09-05)

- 20 new offline tests (adapter parity matrix with mocked SDKs incl.
  gateway base_url + json_object mapping + auth-error classification,
  resolver routing tenant/platform/rotation/cache-hit, missing-encryption-
  key raises instead of falling back, control-plane outage fails open to
  platform, no-fallback policy (tenant auth error → LLMBYOKMisconfigured,
  platform auth error → raw), audit attribution fidelity, embeddings
  platform/tenant/anthropic-tenant routing, storage contract incl.
  crypto-in-SQL binding and masked reads, validation sanitization);
  updated audit + embeddings tests for the new columns/kwarg. Full suite:
  349 passed / 1 pre-existing (Cube-dependent, long-verified on HEAD)
- Live stack (dev DB, genbi_app role): app_crypto encrypt→decrypt roundtrip
  exact; set_provider_config → masked row (v2, last4, api_key never
  present) with ciphertext opaque; resolver → tenant/openai with decrypted
  plaintext matching; LLMClient._build_llm → OpenAIChat for the tenant;
  wrong-key decrypt fails loudly; status=disabled → platform; delete →
  platform (the explicit revert), get → None
- Migration 0012 + paired rls (pgcrypto app_crypto SECURITY DEFINER
  encrypt/decrypt with key-as-bind, tenant recipe on
  tenant_llm_providers, genbi_app schema USAGE) applied to dev + test DBs
