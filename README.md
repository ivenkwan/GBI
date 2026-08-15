# GenBI — Generative BI Platform

**Natural language → SQL → chart + narrative. Governed, explainable, multi-tenant.**

GenBI lets business users query enterprise data warehouses in plain English and
returns a validated SQL query, a rendered chart, and a written insight — all in
a single interaction, with row-level security, PII masking, and full audit
tracing enforced on every request.

> **Status:** actively developed scaffold. The agent pipeline, semantic layer,
> and governance controls are implemented; see [Project Status](#project-status)
> for what is verified vs. in progress.

---

## Table of Contents

- [Quick Start](#quick-start)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Common Tasks](#common-tasks)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project Status](#project-status)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) + Compose v2 | latest | Runs the full stack |
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager (backend) |
| [pnpm](https://pnpm.io/) | latest | Node package manager (frontend) |
| Node.js | 22+ | Frontend runtime |
| Python | 3.12+ | Backend runtime |

### One-command setup

```bash
git clone <repo-url> && cd GBI
make setup
```

`make setup` checks prerequisites, generates `.env` files with random secrets,
installs dependencies, builds Docker images, starts the stack, runs migrations,
and verifies every service is healthy. On success it prints the access URLs.

### Demo credentials

A dev-only user is seeded into a fresh database (via `infra/postgres/init.sql`):

| Email | Password | Roles |
|---|---|---|
| `admin@genbi.local` | `admin123` | `admin`, `user` |

> Dev-only — remove or rotate before any production deployment. Existing
> databases created before this seed need `make reset` (init.sql only runs on
> fresh volumes).

### Database roles (enforced tenant isolation)

The backend never connects as a superuser (see
[ADR 006](docs/adr/006-enforced-rls-roles.md)). Roles are created by
`init.sql` on fresh volumes and by Alembic `0002_app_roles` everywhere else:

| Role | Password (dev) | Used by | Can do |
|---|---|---|---|
| `genbi` (owner) | `genbi` | Alembic, admin scripts (`DATABASE_URL_SYNC`) | Everything |
| `genbi_app` | `genbi_app` | Backend runtime + query connector (`DATABASE_URL`) | RLS-bound DML/SELECT; sees only rows matching `app.current_tenant_id` |
| `genbi_auth` | `genbi_auth` | Login endpoint (`DATABASE_URL_AUTH`) | Read `users` across tenants; nothing else |

All dev passwords are fixed defaults — **rotate in production**. Analytics
tables (`sales`, `orders`, …, `web_users`) are FORCE-RLS tenant-scoped like
the metadata tables (Alembic `0003_analytics`).

> **Upgrading an existing stack:** `make migrate` creates the roles and
> analytics tables, then regenerate env files so the runtime uses the new
> role URLs: `scripts/gen-env.sh --force && make restart`. Old seed data with
> an analytics `users` table conflicts with `web_users` — the cleanest path
> is `make reset` (fresh volume + init.sql) and re-seed.

<details>
<summary><b>Manual setup (if you prefer not to use the Makefile)</b></summary>

```bash
# 1. Generate env files (creates backend/.env and semantic/cube/.env)
scripts/gen-env.sh

# 2. Install host-side dev deps
cd backend && uv sync --dev && cd ..
cd frontend && pnpm install && cd ..

# 3. Build and start the stack
docker compose -f infra/docker-compose.dev.yml up -d --build

# 4. Apply migrations
docker compose -f infra/docker-compose.dev.yml exec backend uv run alembic upgrade head

# 5. Verify
scripts/verify.sh
```

</details>

### Access the platform

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:3000 | Chat UI with SSE streaming |
| Backend API (Swagger) | http://localhost:8000/docs | Interactive OpenAPI docs |
| Health | http://localhost:8000/api/v1/health | Liveness + readiness probes |
| Cube (semantic layer) | http://localhost:4000 | Metrics API |
| Prometheus | http://localhost:9090 | Metrics dashboard |
| Grafana | http://localhost:3001 | `admin` / `admin` |

You'll need to set `ANTHROPIC_API_KEY` in `backend/.env` to enable the LLM
features (NL2SQL, narrative generation).

---

## What It Does

A single user query flows through a governed multi-agent pipeline:

```
User Query (NL)
  → RouterAgent        classify intent, build dispatch plan
    → NL2SQLAgent      generate SQL with pgvector schema context + Cube metrics
      → ValidationAgent   read-only + destructive-pattern safety gate
        → Connector        execute (read-only, tenant-scoped, 30s timeout)
          → ChartGenAgent   Flint chart spec + render + hallucination check
            → NarrativeAgent   written insight paragraph
              → AuditLog          persist full trace
```

**Governance at every step:**
- **Read-only enforcement** — `ValidationAgent` rejects any non-SELECT or
  destructive SQL before execution; the connector sets
  `SET TRANSACTION READ ONLY` at the DB level.
- **Multi-tenant isolation** — PostgreSQL row-level security (RLS) with
  `FORCE` scopes every query by `tenant_id` from the JWT.
- **PII masking** — sensitive columns are masked before results reach agents
  or the cache, so no PII ever enters LLM context.
- **Audit trail** — every LLM call logs tokens, latency, model version, and a
  prompt hash to the `audit_log` table.
- **Chart hallucination detection** — a deterministic validator checks chart
  specs against the underlying data and auto-corrects common errors.

---

## Architecture

GenBI is built on two open-source foundations, with a semantic layer,
governance controls, and a Next.js frontend layered on top.

- **[DB-GPT](https://github.com/eosphoros-ai/DB-GPT)** — agentic AI data
  application framework (Text2SQL, sandboxed execution, RAG).
- **[Flint Chart](https://github.com/microsoft/flint-chart)** — MCP-native
  chart rendering (unified spec → Vega-Lite / ECharts / Chart.js).

```
┌─────────────────────────────────────────────────────┐
│  Interface      Next.js 15 · FastAPI REST · SSE     │
├─────────────────────────────────────────────────────┤
│  Orchestration  LangGraph agents (NL2SQL, ChartGen, │
│                 Narrative, Router, Validation)       │
├─────────────────────────────────────────────────────┤
│  Semantic       Cube-native metric catalog → Cube API│
├─────────────────────────────────────────────────────┤
│  Data           PostgreSQL · pgvector · Apache AGE   │
│                 (connectors: read-only, tenant-scoped)│
├─────────────────────────────────────────────────────┤
│  Governance     RLS · PII masking · audit log · JWT  │
└─────────────────────────────────────────────────────┘
```

For the full design rationale, see the
[Architecture Overview](docs/architecture-overview.md) and the
[Architecture Decision Records](#architecture-decision-records-adrs).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 · FastAPI · Uvicorn / Gunicorn · Pydantic v2 · SQLAlchemy 2.0 (async) |
| **LLM** | Anthropic Claude (Opus for SQL reasoning, Haiku for speed) · LangChain / LangGraph · LlamaIndex |
| **Semantic layer** | Cube.dev (headless BI, native data models) |
| **Databases** | PostgreSQL 16 · pgvector (schema embeddings) · Apache AGE (lineage graph) · Redis (cache) |
| **Frontend** | Next.js 15 (App Router) · TypeScript 5.9 · Tailwind CSS v4 · shadcn/ui · Zod |
| **Charts** | Flint MCP → Vega-Lite / ECharts / Chart.js |
| **Observability** | OpenTelemetry · Langfuse (LLM tracing) · Prometheus + Grafana |
| **Auth** | JWT + RBAC · PostgreSQL row-level security |
| **CI/CD** | GitHub Actions · Docker Compose |

**Package managers:** `uv` for Python (never `pip`), `pnpm` for Node (never
`npm`/`yarn`). See [`CLAUDE.md`](CLAUDE.md) §2 for the full conventions.

---

## Project Structure

```
genbi/
├── backend/               FastAPI app + LangGraph agents
│   ├── app/
│   │   ├── agents/        NL2SQL, ChartGen, Narrative, Router, Validation
│   │   ├── api/v1/        Versioned REST routers (/api/v1/*)
│   │   ├── connectors/    Read-only SQLAlchemy DB connectors
│   │   ├── core/          config, auth, cache, llm_client, masking, logging
│   │   ├── db/            ORM models, sessions, Alembic migrations
│   │   ├── semantic/      Cube.dev client
│   │   └── services/      chat_service (pipeline orchestrator)
│   ├── tests/             unit, integration, golden evals
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/              Next.js 15 + shadcn/ui
│   └── src/{app,components,lib,types}/
├── semantic/              Cube.dev project + metric catalog (schema/)
├── infra/                 Docker Compose (dev + prod), Postgres init, Prometheus
│   └── postgres/Dockerfile   Custom image: pgvector + Apache AGE
├── scripts/               setup.sh, gen-env.sh, verify.sh, embed_schema.py
├── docs/                  Architecture docs + ADRs + OpenAPI
├── Makefile               setup / up / down / verify / migrate / seed / ...
└── CLAUDE.md              AI coding-assistant context (conventions + rules)
```

---

## Documentation

### Start here
- **[ docs/index.md ](docs/index.md)** — curated entry point with quick links

### Architecture & Design
- [Architecture Overview](docs/architecture-overview.md) — four-tier design, data flow, tech stack
- [Agent System](docs/agent-system.md) — multi-agent LangGraph pipeline, agent roster, safety gate
- [Core Services](docs/core-services.md) — config, LLM client, cache, auth, PII masking, observability
- [Data Layer](docs/data-layer.md) — ORM models, read-only connectors, AGE graph schema, migrations
- [Semantic Layer](docs/semantic-layer.md) — Cube-native catalog → Cube.dev → Python client
- [Frontend Guide](docs/frontend-guide.md) — Next.js App Router, shadcn/ui, SSE chat, Zod validators

### API
- [API Reference](docs/api-reference.md) — REST endpoints, request/response schemas, SSE streaming
- [OpenAPI Spec](docs/api/openapi.yaml) — machine-readable API contract

### Operations
- [Infrastructure](docs/infrastructure.md) — Docker Compose, CI/CD, env vars, scripts

### Architecture Decision Records (ADRs)
- [ADR 001 — Dual chart stack](docs/adr/001-dual-chart-stack.md) — Flint MCP + AntV G2
- [ADR 002 — Agent architecture](docs/adr/002-agent-architecture.md) — LangGraph multi-agent topology
- [ADR 003 — vis-flint protocol](docs/adr/003-vis-flint-protocol.md) — chart embedding protocol
- [ADR 004 — Flint bridge fallback](docs/adr/004-flint-bridge-fallback.md) — render fallback path
- [ADR 005 — AGE + pgvector image](docs/adr/005-age-and-pgvector-image.md) — custom Postgres image for both extensions
- [ADR 006 — Enforced RLS roles](docs/adr/006-enforced-rls-roles.md) — non-superuser runtime roles, RLS actually enforced
- [ADR 007 — Cube-native semantic layer](docs/adr/007-cube-native-semantic-layer.md) — metric catalog as Cube data models (dbt tier dropped)
- [ADR 008 — Per-tenant Cube data path](docs/adr/008-per-tenant-cube-data-path.md) — JWT tenant claims → per-tenant driver GUC → RLS, fail-closed

### AI assistant context
- [CLAUDE.md](CLAUDE.md) — full project context, hard rules, and conventions for AI coding tools

---

## Common Tasks

All tasks are wrapped in the [`Makefile`](Makefile). Run `make help` for the
full list.

| Task | Command | Notes |
|---|---|---|
| First-time setup | `make setup` | Prereqs → secrets → deps → build → migrate → verify |
| Start the stack | `make up` | Dev compose, detached |
| Stop the stack | `make down` | Keeps data volumes |
| Tail logs | `make logs` | All services, Ctrl-C to exit |
| Service status | `make ps` | Health + state |
| Smoke test | `make verify` | Health endpoints + DB + Redis + AGE |
| Apply migrations | `make migrate` | `alembic upgrade head` in backend |
| Load test data | `make seed` | Synthetic 10-table dataset |
| Regenerate secrets | `make secrets` | New random JWT / Cube / Fernet keys |
| **Nuke + restart** | `make reset` | ⚠️ `down -v && up` — destroys data |

### Adding a new metric

1. Define it in `semantic/cube/schema/{domain}.yml` (Cube data-model YAML).
2. Run `uv run pytest backend/tests/semantic/test_catalog.py` — structural invariants.
3. Restart Cube (`make restart`) — `/meta` reflects the change (5-min client cache).
4. Re-embed the schema: `uv run python scripts/embed_schema.py`.

See the [Semantic Layer docs](docs/semantic-layer.md) for details.

### Adding a new agent

1. Create `backend/app/agents/{name}_agent.py` extending `BaseAgent`.
2. Register in `backend/app/agents/registry.py`.
3. Add tests in `backend/tests/agents/` with mocked LLM (`tests/fixtures/llm_mock.py`).
4. Update `RouterAgent`'s dispatch table.

See the [Agent System docs](docs/agent-system.md) for the full protocol.

---

## Configuration

All configuration is via environment variables, loaded by
[`backend/app/core/config.py`](backend/app/core/config.py) with Pydantic
Settings. Never commit `.env` files.

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | Claude API access |
| `DATABASE_URL` | yes | `postgresql+asyncpg://...` |
| `REDIS_URL` | yes | `redis://host:6379/0` |
| `JWT_SECRET_KEY` | yes (prod) | Random 32+ hex; **boot fails if default in non-dev** |
| `CUBE_API_URL` / `CUBE_API_SECRET` | yes | Cube.dev semantic layer |
| `TENANT_ENCRYPTION_KEY` | yes (prod) | Fernet key for tenant secrets |
| `LANGFUSE_*` | optional | LLM tracing (disabled if unset) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | optional | OTel collector |

`scripts/gen-env.sh` (via `make setup` / `make secrets`) generates
`backend/.env` and `semantic/cube/.env` from `.env.example` with random secrets.
See `.env.example` for the full list with defaults.

---

## Testing

```bash
# Backend unit + integration tests (mocked LLM, no live services)
cd backend && uv run pytest tests/ -v -m "not e2e"

# Golden NL2SQL eval gate (20 queries, 90% accuracy threshold)
cd backend && uv run pytest tests/evals/ -v

# Lint + format check
cd backend && uv run ruff check . && uv run ruff format --check .

# Frontend
cd frontend && pnpm lint && pnpm typecheck
```

The golden NL2SQL suite is a **merge gate**: 20 NL/SQL pairs scored across
three tolerance levels (exact / fuzzy / semantic), requiring ≥90% suite
accuracy. The LLM transport is mocked, but the agent's prompt-building, JSON
parsing, and destructive-pattern detection all run for real. See
[`backend/tests/evals/`](backend/tests/evals) and
[CLAUDE.md §9](CLAUDE.md) for the testing philosophy.

---

## Project Status

| Area | Status | Notes |
|---|---|---|
| Agent pipeline (NL→SQL→Chart→Narrative) | ✅ Implemented | Sync + SSE streaming |
| Validation safety gate | ✅ Hardened | EXPLAIN-backed row estimates + >1M-row confirmation flow (Phase 13); deterministic pattern gate remains |
| Semantic layer (Cube-native catalog) | ✅ Implemented | 10 cubes / 23 measures; tenant-scoped /metrics/query + Explore page (ADR 007/008) |
| Governance: audit trail + login throttling | ✅ Implemented | Every LLM call audited (tenant-scoped, fail-open); 5 failed logins → 429 (Phase 12) |
| NL2SQL schema grounding (pgvector retrieval) | ✅ Implemented | Schema context + few-shot into every prompt (Phase 11); needs `embed_schema.py --examples` + OPENAI_API_KEY |
| Multi-tenant RLS + JWT | ✅ Enforced | Non-superuser runtime roles + FORCE RLS on all tenant tables, incl. analytics (ADR 006) |
| PII masking | ✅ Wired | Applied at the execution chokepoint |
| Chart hallucination detection | ✅ Implemented | 6 validation categories + auto-correct |
| Dual-tier cache (L1 LRU + L2 Redis) | ✅ Implemented | Schema, metrics, results, charts |
| Observability (OTel + Langfuse + Prometheus) | ✅ Wired | `/metrics` endpoint on backend |
| Frontend chat UI | ✅ Implemented | SSE streaming, stage rendering, conversation sidebar + multi-turn history (Phase 14) |
| Environment provisioning (`make setup`) | ✅ Implemented | One-command bootstrap |
| End-to-end verification | ✅ Verified | 120 tests pass, `make verify` green, CI builds + eval gate (Phases 7–12) |

> Phase 7 (build & test verification) closed out Phases 5b/6 as VERIFIED.
> Phases 8–12 delivered the auth + chat vertical slice, enforced tenant
> isolation (non-superuser roles, ADR 006), the Cube-native metric catalog
> (ADR 007), tenant-scoped Metrics + Explore (ADR 008), NL2SQL schema
> grounding, and governance (audit trail + login throttling).

> See [`todo.md`](todo.md) for the phase tracker (Phases 1–12) and the
> implementation/verification history.

---

## Contributing

1. Read [CLAUDE.md](CLAUDE.md) first — it codifies the hard rules (security,
   LLM patterns, coding conventions) that every change must respect.
2. Use the package managers (`uv`, `pnpm`) — never `pip` / `npm`.
3. All API routes are versioned under `/api/v1/`.
4. Mock the LLM in tests; never call real APIs in unit/integration tests.
5. Run `make verify` before requesting review.

### Protected files (require security review to change)

Per CLAUDE.md §13, these are gated:
- `backend/app/core/auth.py` — JWT + RBAC
- `backend/app/agents/validation/validation_agent.py` — SQL safety gate
- `backend/app/db/migrations/` — Alembic history (never edit existing files)
- `infra/postgres/init.sql` — DB initialization

---

## License

[MIT](LICENSE) © GenBI contributors.
