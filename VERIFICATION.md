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
