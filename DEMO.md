# GenBI Demo Environment

Everything needed to take a clean machine to a demo-ready GenBI platform —
and back — with one CLI (`scripts/demo.py`, Phase 27). The host side is
stdlib-only: a machine needs just **Docker + Python 3**; all heavy work
runs inside the containers.

```bash
make demo-up      # 1. provision & bring the environment up   (or: python3 scripts/demo.py up)
make demo-seed    # 2. load demo tenants/users/data           (or: scripts/demo.py seed)
make demo-unseed  # 3. remove demo data, baseline intact      (or: scripts/demo.py unseed)
make demo-reset   # 4. factory reset to fresh defaults        (or: scripts/demo.py reset)
make demo-status  # health + demo state + credentials         (or: scripts/demo.py status)
```

## Quickstart (from zero to a demo in four commands)

```bash
git clone https://github.com/ivenkwan/GBI && cd GBI
make demo-up        # builds images (first run compiles AGE — grab a coffee), starts everything, verifies
make demo-seed      # creates demo tenants, users, analytics, wiki, report, dashboard
open http://localhost:3003
# log in as admin@demo-acme.test (password below)
```

> **Ports.** The frontend listens on **3003** by default (3000 is claimed by
> common local services). If 3003 is busy the CLI auto-picks the next free
> port, threads it through compose + verify.sh, and adjusts the backend's
> `CORS_ORIGINS` — `make demo-status` always prints the live URL. Pin a port
> with `GENBI_HOST_FRONTEND_PORT` (same pattern for pg/redis/cube/grafana:
> `GENBI_HOST_*_PORT`). The backend stays on 8000.
>
> **Accessing from another machine** (LAN IP / SSH tunnel): the browser talks
> only to the frontend origin — `/api/v1` is proxied server-side to the
> backend (`next.config.js` rewrites) — so `http://<host>:3003` works from
> anywhere that can reach the host, no CORS or port-forwarding gymnastics.
> If a page ever renders unstyled after a rebuild, hard-refresh
> (Ctrl+Shift+R) to drop stale asset references.

## What each command does

### `demo up` — provision & bring the environment up

Idempotent — a healthy stack is a no-op. On a cold machine it:

1. Checks Docker is reachable and warns (non-fatally) about missing
   `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`.
2. Generates `backend/.env` + `semantic/cube/.env` via `scripts/gen-env.sh`
   (random secrets; existing files are never overwritten).
3. Builds the images — or with `--pull`, uses the CI-published pgvector+AGE
   image to skip the slow AGE source compile.
4. Starts postgres + redis, then the full stack; waits for real health.
5. On a fresh volume, stamps Alembic at `0001_baseline` (init.sql owns the
   baseline), then applies `alembic upgrade head` + every
   `infra/postgres/rls/*.sql`.
6. Runs `scripts/verify.sh` — the command fails loudly if smoke checks are red.

```bash
python3 scripts/demo.py up --pull        # prebuilt AGE image (requires registry access)
python3 scripts/demo.py up --no-verify   # skip the smoke gate
```

### `demo seed` — provision demo data

Creates dedicated demo tenants — **`Acme Analytics`** (`demo-acme`) and
**`Globex Retail`** (`demo-globex`)`) — marked `tenants.settings = {"demo": true}`
so removal is precise. The bootstrap tenant (`admin@genbi.local`) is never
touched. Per demo tenant:

- 3 users (admin / analyst / viewer), bcrypt-hashed shared password `Demo123!`
- Deterministic analytics across all 10 tables (9,122 rows/tenant; fixed
  seed = the same numbers at every demo — `--random` opts out)
- Schema embeddings + golden NL2SQL few-shot examples
  (`scripts/embed_schema.py --tenant-id`) when `OPENAI_API_KEY` is set —
  otherwise skipped with a warning (chat still works)
- 3 wiki pages, a 3-section report with real chart specs computed from the
  seeded rows, a dashboard pinning those sections, and a sample conversation
- Tenant-scoped Redis caches purged so fresh queries see fresh data

Re-running `demo seed` **replaces** existing demo tenants (decommission +
recreate). `--append` keeps them instead.

```bash
python3 scripts/demo.py seed --tenants 3          # a third generated tenant
python3 scripts/demo.py seed --seed 7             # a different (still stable) dataset
python3 scripts/demo.py seed --random             # fresh random data each run
python3 scripts/demo.py seed --append --skip-embeddings
```

### `demo unseed` — remove demo data

Finds every `settings.demo = true` tenant and removes it through the same
owner-role path as the tenants service: analytics tables are cleaned with
the tenant GUC set, the tenant delete cascades users/content via the FK
CASCADEs, and an `admin_audit` row records the removal. Post-checks assert
zero demo tenants remain and the bootstrap tenant + admin are intact.

Audit history (`audit_log`, `admin_audit`) is retained by design —
`demo reset` is the true clean slate.

### `demo reset` — everything back to original defaults

Destructive (asks for confirmation, or `--yes`):

1. `docker compose down -v` — volumes (database, chart data) are destroyed.
2. Regenerates all secrets via `gen-env.sh --force`, **preserving
   user-supplied API keys** (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `LANGFUSE_*`) from your previous `backend/.env` — `--nuke-env` wipes
   them too.
3. Fresh bring-up: init.sql re-seeds the baseline (`admin@genbi.local` /
   `admin123`), migrations + RLS reapply, verify.sh runs.

```bash
python3 scripts/demo.py reset --yes            # no prompt
python3 scripts/demo.py reset --yes --nuke-env # also wipe preserved API keys
```

## Credentials

| User | Password | Tenant | Roles |
|---|---|---|---|
| `admin@demo-acme.test` | `Demo123!` | Acme Analytics | admin, user |
| `analyst@demo-acme.test` | `Demo123!` | Acme Analytics | user |
| `viewer@demo-acme.test` | `Demo123!` | Acme Analytics | viewer (read-lookups) |
| `admin@demo-globex.test` | `Demo123!` | Globex Retail | admin, user |
| `admin@genbi.local` | `admin123` | default (bootstrap) | admin, user — fresh volumes only |

All demo logins also work against the API:
`POST /api/v1/auth/login {"email": "admin@demo-acme.test", "password": "Demo123!"}`.

## Suggested demo script

1. Log in as the **Acme admin** → ask Chat: *"Show me revenue by region for 2025"*.
2. Open **Reports** → *Quarterly Revenue Overview* → pin sections are already
   on the **Dashboard**.
3. Open **Wiki** → *Metrics Glossary* — the assistant uses these definitions.
4. Log in as the **Globex admin** → the same query returns Globex's numbers
   only (cross-tenant isolation, enforced by RLS).
5. Admin portal: grant yourself platform admin (`make admin-create`) to show
   tenant lifecycle, spend attribution, and audit feeds.

## Capabilities & limitations

| Capability | Needs | Without it |
|---|---|---|
| Stack, login, explore, wiki, dashboards, reports browsing | Docker | — |
| LLM chat (NL → SQL → chart → narrative) | `ANTHROPIC_API_KEY` in `backend/.env` | pipeline degrades with a clear error |
| Schema grounding + few-shot (better NL2SQL) | `OPENAI_API_KEY` | `demo seed` skips embeddings with a warning |
| Deterministic numbers across demos | default fixed seed (42) | use `--random` for fresh data |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker compose build` slow on first run | The pgvector+AGE image compiles Apache AGE from source. With registry access to the CI image: `scripts/demo.py up --pull`. |
| `demo seed` says stack not up | `make demo-up` first; check `make demo-status`. |
| Login fails for demo users after re-seed | JWT secrets were regenerated — log in again with the freshly printed credentials. |
| Metric queries return 0 rows | The demo tenant has data; the **bootstrap** tenant does not. Log in as a demo user, or `make seed` for the default tenant. |
| Verify fails on readiness after reset | Services settle for ~30s; re-run `make demo-status` / `make verify`. |

## How it fits together

- Host CLI: `scripts/demo.py` (stdlib-only) + `scripts/demo/common.py`
- Deterministic dataset: `scripts/demo/dataset.py` (pure stdlib, unit-tested)
- In-container DB work: `scripts/demo/ops.py` (owner role + tenant GUC,
  the `make seed` pattern — `scripts/` is bind-mounted into the backend)
- Marker: `tenants.settings->>'demo' = 'true'` is the single source of truth
  for what `unseed` removes.
- Offline tests: `backend/tests/demo/` · Live-cycle record: `VERIFICATION.md`
