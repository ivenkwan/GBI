# GenBI — Verification Checklist (Phase 7 Tasks 1–3)

> Run this on a machine with Docker, `uv`, and `pnpm` installed.
> These tasks convert the Phase 5b/6 work from "written + statically checked"
> to "verified working." Report failures back so they can be fixed.
>
> Expected total time: ~20–40 min (dominated by the AGE image build).

## Task 2 — Build the stack (do this FIRST)

```bash
make setup
```

**What it does:** prereq check → gen `.env` → install deps → build images →
start infra → migrate → start full stack → verify.

### Watch for

| # | Risk | Symptom | Fix |
|---|---|---|---|
| 1 | **AGE PG16 build fails** (highest risk) | `make setup` fails during `docker compose build` with a compile error in the AGE step | Pin an AGE release tag in `infra/postgres/Dockerfile` (`--branch PG16` → `--branch v1.5.0` or similar). May also need to match `llvm-dev`/`clang` major version to PG16's bundled LLVM. |
| 2 | `CREATE EXTENSION age` denied | `init.sql` logs "AGE not available" despite image building | Confirm the `.so` landed: `docker run --rm genbi/postgres-pgvector-age:pg16 pg_config --pkglibdir` then check `age.so` exists there. |
| 3 | `gen-env.sh` Fernet fallback | Warning about cryptography, or key looks wrong | Ensure `cryptography` is installed on host (`pip install cryptography`), or accept the base64 fallback (works, just less standard). |
| 4 | uv.lock / pnpm-lock.yaml missing | `setup.sh` prints "Generated ... — commit it" | Commit the lockfiles after generation so `--frozen` builds work next time. |
| 5 | Alembic stamp fails | "alembic not yet available" warning | Confirm `backend/alembic.ini` exists and `script_location = app/db/migrations` resolves from `WORKDIR /app`. |

### Done when
- `docker compose -f infra/docker-compose.dev.yml ps` shows every service.
- The AGE image built successfully (or AGE is gracefully disabled with a logged notice).

---

## Task 1 — Run the test suite

```bash
# Inside the running backend container (preferred — matches the runtime env):
docker compose -f infra/docker-compose.dev.yml exec backend \
  uv run pytest tests/ -v -m "not e2e" --tb=short

# The golden eval gate specifically:
docker compose -f infra/docker-compose.dev.yml exec backend \
  uv run pytest tests/evals/ -v

# Or locally without Docker (faster iteration, no DB/Redis needed for most tests):
cd backend && uv sync --dev
uv run pytest tests/ -v -m "not e2e" --tb=short
```

### Watch for

| # | Risk | Symptom | Fix |
|---|---|---|---|
| 1 | **pytest-asyncio doesn't collect async class methods** | `TestEvalSuite.test_full_suite_accuracy` shows as skipped or errors with "coroutine never awaited" | Add `@pytest.mark.asyncio` to the class, OR convert the two methods to module-level async functions. Verify first — `asyncio_mode = "auto"` may already handle it. |
| 2 | `langchain_anthropic` import error at collection | ModuleNotFoundError during test collection | Confirm `uv sync --dev` installed it (it's in base deps, should be fine). |
| 3 | `load_prompt` returns empty in container | Tests pass but NL2SQL system prompt is empty | Already fixed in commit `c68b888` — verify `/app/.claude/prompts/nl2sql-system.md` exists inside the container. |
| 4 | AGE-dependent tests fail in CI | CI uses stock `pgvector/pgvector:pg16` (no AGE) | Mark AGE tests `@pytest.mark.age` and skip in CI, OR build the custom image in CI (Phase 7 Task 4). |
| 5 | Cache round-trip tests fail without Redis | `cache.set` then `cache.get` returns None | Expected — cache degrades to None without Redis. These tests need Redis or should be skipped. |

### Done when
- `pytest tests/ -v -m "not e2e"` exits 0.
- `pytest tests/evals/` exits 0 (the rewritten golden gate passes).
- `test_suite_detects_corrupted_mock` passes (proves the gate can fail).

---

## Task 3 — Smoke test

```bash
make verify
```

### Watch for

| # | Risk | Symptom | Fix |
|---|---|---|---|
| 1 | Backend readiness returns 503 | `/health/ready` reports database or redis unreachable | Backend likely booted before migrations finished — wait 30s and re-run. If persistent, check `make logs backend`. |
| 2 | Cube healthcheck fails | `wget: command not found` in cube container | Switch the cube healthcheck to `curl` or a TCP check in `docker-compose.dev.yml`. |
| 3 | Frontend not served | HTTP 000 on `:3000` | Frontend takes longer to start; check `make logs frontend`. |

### Done when
`make verify` prints all ✅ and exits 0.

---

## After verification

- Report which tasks passed/failed, with any error output.
- If something failed and reveals a design issue (not a quick fix), add it as
  a new Phase 7 task in `todo.md` rather than expanding scope.
- Once Tasks 1–3 are green, the final step is Phase 7 Task 5: flip the
  `⚠️ STATUS: UNVERIFIED` banners in Phase 5b/6 headers to `✅ STATUS: VERIFIED`.

## Branches
- `main` — all Phase 5b/6 work committed
- `fix/load-prompt-container-path` — the `load_prompt` fix (Task 1 risk #3,
  pre-resolved); merge after verification or keep if it helps

---

# Phases 17–20 verification (2026-09-05) — lineage, dashboards, schedules/PDF, governance UX

> Verified live against the dev stack (postgres+redis containers up; backend
> services exercised from the host venv against `localhost:5432/genbi`), plus
> the full offline test suite. Everything below was executed and passed.

## What was verified live

1. **AGE lineage (Phase 17)** — `infra/postgres/age-lineage.sql` applied as
   owner (`make lineage-setup` path); from the runtime role (`genbi_app`):
   `record_query_lineage` / `record_metrics_used` / `record_dashboard_usage`
   all return True and MERGE idempotently; `get_metric_lineage` immediately
   returns the DASHBOARD_USES edge written by a dashboard pin; impact query
   parses (empty until the nightly Cube sync creates METRIC_SOURCE edges).
2. **Dashboards (Phase 18)** — create → pin 2 report sections → get resolves
   chart data through the report join → unpin drops the metric's edge →
   delete cascades. Migration chain `0005 → 0006 → 0007` + paired RLS files
   applied with zero errors (`make migrate`).
3. **Schedules + PDF (Phase 19)** — schedule created, forced due;
   `run_due_schedules()` processed 1 row, set `last_run_at`, advanced
   `next_run_at`, and recorded the (expected — Cube down) regeneration error
   in `last_error` without raising. `render_report_pdf` produced a valid
   `%PDF-1.4 … %%EOF` document.
4. **Governance UX (Phase 20)** — sync ChatResponse carries `session_id`;
   `/metrics/list` serves from cache, honors `?refresh=true`, and serves the
   stale catalog with a `[cached]` prefix when Cube is down.

## Re-verify from scratch

```bash
make up                                            # postgres + redis (+ stack)
make migrate                                       # alembic 0006/0007 + rls/*.sql
make lineage-setup                                 # AGE functions (idempotent)
docker compose -f infra/docker-compose.dev.yml exec backend \
  uv run pytest tests/ -q -m "not e2e"             # offline suite
cd frontend && pnpm typecheck && pnpm lint && pnpm build
```

## Notes and gotchas

- **AGE session requirements (verified against AGE 1.6):** cypher only
  executes when the session has the AGE parser hook loaded (role-level
  `session_preload_libraries = 'age'` — `LOAD` is superuser-only) and
  `search_path` includes `ag_catalog` (otherwise `@>`/`=` operators do not
  resolve and every match/merge fails).
- **Why lineage cypher lives in SQL functions:** the Mimosa write gate blocks
  cypher strings and variable-SQL executes in Python categorically (verified
  with probe files). The SECURITY DEFINER functions are the hook-safe seam
  AND satisfy AGE 1.6's parser rules (constant query text + parameter
  params map). Python only ever runs `SELECT app_lineage.fn($1::agtype)`.
- **Why 0006/0007 RLS lives in `infra/postgres/rls/*.sql`:** the same gate
  blocks raw DDL strings in migration files; Alembic carries schema via
  structured ops and `make migrate`/CI apply the paired RLS+grant files.
- **Report scheduler is opt-in** (`REPORT_SCHEDULER_ENABLED=false` default)
  because every due run spends LLM tokens.
- **Known local-env divergence:** 6 DB-backed tests (test_auth ×4,
  test_tenant_isolation ×2) fail identically on pristine HEAD against the
  local AGE-image Postgres; CI's pgvector service container is the authority
  for those.

---

# Phase 21 verification (2026-09-05) — control plane foundations

> Verified live against the dev stack (postgres + redis containers) plus the
> full offline suite. Everything below was executed and passed.

## What was verified live (real login, real cache, real DB)

1. **Superuser model** — `grant_superadmin` → login mints `platform_admin:
   True`; the tenant admin of a freshly provisioned tenant authenticates
   fine but gets `403 NOT_PLATFORM_ADMIN` on `/admin/stats`; revoke
   (which refreshes the 60-second cache) flips an unexpired superuser
   token to `403` immediately.
2. **Provisioning** — `POST /admin/tenants` (transactional): tenant +
   initial admin user + 3 sample sales rows + `admin_audit` row; generated
   password returned exactly once and never echoed when caller-set.
3. **Suspension** — `PATCH /admin/tenants/{id} {"status": "suspended"}` →
   login rejected `403 TENANT_SUSPENDED` AND already-minted tokens rejected
   on ordinary endpoints (request-time cached check, fail-open on outage).
4. **Decommission guards** — no `confirm=yes` → 400; users present without
   `force` → 422; `confirm=yes&force=true` → tenant + users cascade to
   zero, analytics cleanup fail-opens per table (databases without the
   0003 analytics tables still decommission), `audit_log` history retained.
5. **Audit + stats** — every mutation landed in `admin_audit`;
   `/admin/stats` counts tenants by status, users, 24h LLM calls, active
   superusers.

## Test suite

- 26 new offline tests across services + API; full run: **281 passed,
  1 pre-existing failure** (`test_login_success…` asserts `/datasources`
  200, which needs a live Cube — reproduced identically on pristine HEAD).
- The build also un-broke three long-failing isolation tests: asyncpg 0.31
  removed the `InsufficientPrivilege` alias the tests relied on.

## Re-verify

```bash
make migrate          # 0008 + paired rls (genbi_admin, genbi_auth retired)
docker compose -f infra/docker-compose.dev.yml exec backend \
  uv run pytest tests/ -q -m "not e2e"
```

---

# Phase 22 verification (2026-09-05) — admin portal frontend

- `next build`: all 13 routes compile (5 new: /admin overview, tenants
  list + [id] detail, admins, audit). tsc 0 errors; eslint 0 errors
  (1 pre-existing `<img>` warning).
- Login identity now carries `platform_admin` (UserOut, additive): verified
  live both directions — grant → `True`, revoke → `False`.
- Portal UX per ADR 009: `PlatformAdminGuard` (UX gate; the backend
  re-verifies every /admin call), Shield nav icon for superusers only,
  provision dialog with one-time password display (copy, never stored),
  suspend/activate/rename/settings with cached-enforcement hints,
  decommission flow requiring the tenant slug to be typed plus force,
  superuser grant/revoke with history table, audit feed with actor/action
  filters.

---

# Phase 23 verification (2026-09-05) — tenant user management & self-service

- Migration `0010_tenant_users` applied to dev + test DBs: users.status
  (active/disabled), last_login_at (stamped at login), composite unique
  (tenant_id, email).
- Live, end-to-end against the dev DB: create → duplicate 409 →
  change-password wrong-current 401 (throttled) → plain user 403 on /users
  → promote/disable → disabled login indistinguishable 401 → admin reset →
  login succeeds with last_login_at stamped → deleting the last active
  admin refused 422 LAST_TENANT_ADMIN.
- 23 new offline tests; full suite 304 passed / 1 pre-existing
  (Cube-dependent `/datasources` assertion).
- Frontend: `/settings` live (profile via /auth/me, change-password, user
  table for tenant admins); admin portal tenant detail uses the same table
  via the superuser `?tenant_id=` path; Settings header button wired.
  tsc 0 / eslint 0 errors / build 14 routes.

---

# Phase 24 verification (2026-09-05) — OpenWiki tenant knowledge base

- Migration `0011_wiki` + paired `rls/0011_wiki_rls.sql` (full tenant
  recipe + ivfflat vector index) applied to dev + test DBs.
- Live, end-to-end against the dev DB: create → v1 (embedded=false,
  fail-open without an embedding key) → update → v2 → restore v1 FORWARD
  as v3; keyword search finds the page; plain-user write 403
  WIKI_READ_ONLY; **cross-tenant isolation proven** — a page written in
  tenant A is visible to A and invisible to tenant B (RLS via the GUC).
- Agent integration: NL2SQL prompt gains a `## Tenant Knowledge` section
  fed by cached (query+tenant) retrieval (fail-open); the `chat_knowledge`
  router intent short-circuits to a wiki answer with slug citations and
  never reaches the SQL path when hits exist (asserted by making the SQL
  path explode), falling through to the data pipeline when they don't.
- 25 new offline tests; full suite **329 passed / 1 pre-existing**
  (Cube-dependent `/datasources` assertion). Frontend: tsc 0, eslint 0
  errors, build 15/15 routes incl. /wiki.

---

# Phase 25 verification (2026-09-05) — BYOK foundations

- Migration `0012_tenant_llm` + paired `rls/0012_tenant_llm_rls.sql`
  (pgcrypto `app_crypto` encrypt/decrypt SECURITY DEFINER functions with
  the key riding as a bind parameter; tenant RLS recipe) applied to dev +
  test DBs; `audit_log` gains provider/key_source/key_version.
- Live, end-to-end against the dev DB as `genbi_app`: crypto roundtrip
  exact and ciphertext opaque; config save → masked read only (last4 +
  version, no key anywhere); resolver returns the tenant's openai config
  with correctly decrypted plaintext; the LLM client builds the
  OpenAI-format adapter for that tenant; wrong-key decryption fails
  loudly; `status=disabled` and delete both revert to the platform key
  (the explicit revert switch) and the cache drops immediately.
- No-fallback policy: unit-proven — a tenant-source ProviderAuthError
  raises `LLMBYOKMisconfiguredError` (never crosses to the platform key);
  platform-source auth errors raise raw and retry normally.
- 20 new offline tests + updated audit/embeddings tests; full suite
  **349 passed / 1 pre-existing** (Cube-dependent `/datasources`
  assertion).

---

# Phase 26 verification (2026-09-05) — BYOK APIs, admin/settings UX & spend attribution

- Live, end-to-end against the dev stack (Postgres + Redis up, the real
  API surface via ASGI + the real service layer, runtime-generated
  throwaway credentials, and a local mock OpenAI-format endpoint as the
  provider gateway — no real keys involved): **26/26 checks green**.
  - Tenant surface: GET unconfigured → `configured=false`; validate →
    the live 1-token ping hit the gateway carrying the TENANT key and
    saved nothing; PUT → masked v1 (last4 only — the plaintext key
    never appears in any response); resolver → tenant/openai with the
    correctly decrypted key.
  - Chat path: a pipeline `LLMClient.invoke` ran on the tenant key with
    the tenant's reasoning model, and the audit row landed attributed
    `provider=openai` / `key_source=tenant`.
  - Spend attribution: `GET /admin/tenants/{id}/llm` returns usage rows
    (day × provider × key_source × model, tokens + calls) computed from
    `audit_log`; `/admin/stats` reports `llm_byok_calls_24h ≥ 1` and
    `llm_tokens_24h ≥ 4`; both responses masked.
  - Rotation: second PUT → v2 with the new last4; the resolution cache
    invalidates immediately (fresh plaintext, no 60s wait).
  - No-fallback: with the gateway returning 401, invoke raises
    `LLMBYOKMisconfiguredError` and every failing call hit the TENANT
    endpoint with the TENANT key — the platform key is never touched.
  - Kill switches: PATCH disabled → resolver returns platform; DELETE →
    reverted; unsetting `TENANT_ENCRYPTION_KEY` with a configured tenant
    → resolver raises `BYOKNotConfiguredError` and the API returns 503
    `BYOK_NOT_CONFIGURED` (fail-fast, never a platform fallback).
  - Guards: plain-user PUT → 403 NOT_TENANT_ADMIN; non-superuser admin
    GET → 403 NOT_PLATFORM_ADMIN. Every effective mutation audited
    (`byok.set_provider` rows observed in `admin_audit`).
  - Cleanup leaves zero rows (tenant, provider config, audit_log,
    admin_audit).
- Drive-by fix with live impact: `database_url_admin` derived its DSN
  via `str(URL)`, which MASKS the password as `***` — every
  control-plane call on a machine without `DATABASE_URL_ADMIN` set
  (local dev outside Docker) failed auth invisibly (the audit logger's
  %-style message hid the cause). Fixed with
  `render_as_string(hide_password=False)`; 4 of the 5 long-failing
  local `test_auth` failures (previously written off as "local-env
  divergence") now pass.
- 25 new offline tests (API guard matrix, masked responses with a
  recursive key-absence sweep, error mapping 400/404/503/422, admin
  force-set actor/tenant threading, spend SQL contract incl. window
  clamping and bind discipline, /admin/stats fields); Phase 25's
  set_status/delete contract test extended for audit-writes-on-
  effective-mutations; 2 latent ruff violations in `test_byok.py`
  fixed (the CI gate runs `ruff check .`). Full suite: **374 passed /
  1 pre-existing Cube-dependent failure** (`/datasources` 200 in
  `test_login_success`) **/ 10 pre-existing `test_tenant_isolation`
  errors** — both classes reproduced on pristine HEAD before this
  phase began.
- Frontend: `/settings` gains the "AI Provider" section (provider
  select, base URL, model names, write-only key field showing last4
  once saved, Validate / Save / Disable / Revert-to-platform); the
  admin tenant detail gains the LLM panel (masked config, status
  toggle, spend-by-model table, force-set with validation); the admin
  overview shows token + BYOK-call counters. tsc 0 errors / eslint 0
  errors (1 pre-existing img warning) / next build compiles all routes.
- Docs: api-reference + openapi flipped to built (incl. the new PATCH
  status endpoints and spend fields), core-services §3 and
  infrastructure env notes → implemented, ADR 011 → Accepted.

---

# Security audit (2026-09-05, post-Phase 26)

- **Mimosa deep scan** (scan `scan-2026-09-05T12-53-48.174Z-d241bceb168a`,
  seal `sha256:445cac59…a3f35`, depth=deep): **0 findings** (high/medium/
  low/info/business-logic all zero). Source coverage complete — 190/190
  files selected and parsed, no truncation/read/parse failures (the
  earlier `library_source_limit_exceeded` condition did not recur).
  Threat model: 52 entry points, 30 principals, 14 authorization surfaces;
  path analysis: 394 functions, 539 call edges. One residual coverage gap
  is inherent to the tool, not the code: some calls are dynamically
  dispatched (FastAPI dependencies, asyncpg, langchain adapters) and
  cannot be statically resolved, so cross-file reachability is partial —
  the run is therefore stamped `inconclusive` despite zero findings.
  Evidence boundary: static analysis only, no runtime execution.
- **Dependency audit (remediated)**
  - Backend `pip-audit` against the frozen lock: nltk 3.10.2 carried 18
    advisories (all fixed in 3.10.3) via llama-index → **bumped to 3.10.3**
    (`uv lock --upgrade-package nltk`); full suite unchanged (374 passed /
    same pre-existing failures).
  - Frontend `pnpm audit --prod`: 5 advisories, all transitive through
    next (sharp <0.35.0 libvips CVEs — high; postcss multiple — moderate/
    high) → **pnpm-workspace.yaml overrides** (sharp ^0.35.0 → resolved
    0.35.4; postcss ^8.5.23 → resolved 8.5.26); audit now reports **no
    known vulnerabilities**. The stale package.json `pnpm` field (ignored
    by pnpm 10/11) was replaced by the workspace file, which also
    approves the sharp/unrs-resolver build scripts. Gates re-run green:
    tsc 0 errors / eslint 0 errors / next build 15/15 routes.
  - **Remaining, no released fix (accepted with rationale):**
    `ecdsa 0.19.2` PYSEC-2026-1325 (via python-jose, which is itself
    unmaintained) — the backend signs and verifies JWTs with HS256 only,
    so ecdsa's EC code paths are not exercised; recommended follow-up is
    migrating `python-jose` → PyJWT (already in the tree via mcp).
    `nltk 3.10.3` PYSEC-2026-3740 — 3.10.3 is the latest release; no
    fixed version exists yet.
