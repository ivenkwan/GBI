# GenBI Platform — Build Progress

> **Last updated:** 2026-07-04 | **Stack tier:** Enterprise | **30/30 tasks complete**

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
