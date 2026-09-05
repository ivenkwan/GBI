# Generative BI Platform — Project Context

> **Owner:** Iven Kwan | **Stack Tier:** Enterprise | **Mode:** Agentic Coding
> This file is the persistent memory layer for Claude Code. Read it fully before touching any code.

---

## 1. Project Overview

A **Generative BI (GenBI) platform** that enables business users to query enterprise data warehouses using natural language, auto-generates visualizations and narrative insights, and delivers governed, explainable analytics at scale.

**Core value proposition:**
- Natural language → SQL → chart + narrative (single interaction cycle)
- Semantic layer as the single source of truth for metrics
- Multi-tenant, role-aware data access with full audit trail
- Deployable on-premise or cloud for regulated industries (FSI, AML/KYC contexts)

**Primary users:** Data analysts, business stakeholders, compliance officers, C-suite  
**Persona:** Users who know *what* they want to see but not *how* to query it

---

## 2. Tech Stack

```
Backend:       Python 3.12 · FastAPI · Uvicorn / Gunicorn
LLM Layer:     Anthropic Claude API (claude-opus-4 for reasoning, claude-haiku-4 for speed)
               LangChain / LangGraph for orchestration and agent loops
               LlamaIndex for semantic indexing and RAG
Semantic Layer: dbt (MetricFlow) + Cube.dev (headless BI / metrics API)
Databases:     PostgreSQL 16 (primary store, metadata, audit)
               Apache AGE (graph queries for lineage & relationship analysis)
               pgvector (schema embeddings, semantic search)
               Redis (query cache, session state)
Vector Store:  pgvector (default) / Weaviate (scale-out option)
Charts:        Vega-Lite (declarative) + Plotly.js (interactive frontend)
Frontend:      Next.js 15 (App Router) · TypeScript 5.9 · Tailwind CSS v4 · shadcn/ui
Auth/RBAC:     FastAPI + JWT + row-level security (PostgreSQL RLS)
               DID/VC-compatible identity hooks (future)
Containerization: Docker + Docker Compose · GitHub Actions CI
Observability:  OpenTelemetry · Langfuse (LLM tracing) · Prometheus + Grafana
```

**Package managers:** `uv` for Python (NOT pip/poetry), `pnpm` for Node (NOT npm/yarn)  
**Python version:** 3.12 — use match/case, walrus operator, typed dicts freely  
**NEVER use:** raw `pip install`, `npm install`, `yarn`

---

## 3. Architecture Layers

```
┌─────────────────────────────────────────────┐
│  Layer 1: Interface (Next.js, REST, Slack)  │
├─────────────────────────────────────────────┤
│  Layer 2: Orchestration (LangGraph Agents)  │
│   ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│   │ NL2SQL   │ │ ChartGen │ │ Narrative  │ │
│   │ Agent    │ │ Agent    │ │ Agent      │ │
│   └──────────┘ └──────────┘ └────────────┘ │
├─────────────────────────────────────────────┤
│  Layer 3: Semantic Layer (dbt + Cube.dev)   │
│  Metrics store · Schema catalog · RLS rules │
├─────────────────────────────────────────────┤
│  Layer 4: Data Retrieval                    │
│  PostgreSQL · Snowflake · Redshift (via     │
│  SQLAlchemy connectors)                     │
├─────────────────────────────────────────────┤
│  Layer 5: Governance & Audit                │
│  Prompt logs · Query lineage · Feedback     │
└─────────────────────────────────────────────┘
```

### Agent Responsibilities
| Agent | Input | Output | Model |
|---|---|---|---|
| `NL2SQLAgent` | User prompt + schema context | SQL query + explanation | claude-opus-4 |
| `ChartGenAgent` | SQL result set + prompt intent | Vega-Lite spec JSON | claude-haiku-4 |
| `NarrativeAgent` | Data + chart + business context | Insight paragraph | claude-haiku-4 |
| `RouterAgent` | Raw user query | Agent dispatch plan | claude-haiku-4 |
| `ValidationAgent` | Generated SQL | Safety check + dry-run | deterministic |

---

## 4. Project File Structure

```
genbi/
├── CLAUDE.md                  ← you are here
├── .claude/
│   ├── rules/
│   │   ├── sql-safety.md      ← SQL injection & destructive query rules
│   │   ├── llm-patterns.md    ← LLM prompt engineering conventions
│   │   └── api-design.md      ← FastAPI route design standards
│   └── skills/
│       ├── add-data-source/   ← how to onboard a new database connector
│       ├── add-agent/         ← how to register a new agent
│       └── deploy/            ← deployment runbook
├── backend/
│   ├── app/
│   │   ├── api/               ← FastAPI routers (versioned: /v1/*)
│   │   ├── agents/            ← LangGraph agent definitions
│   │   ├── semantic/          ← Cube.dev + dbt schema loaders
│   │   ├── connectors/        ← SQLAlchemy DB connectors
│   │   ├── services/          ← business logic (query service, chart service)
│   │   ├── models/            ← Pydantic schemas (NOT SQLAlchemy here)
│   │   ├── db/                ← SQLAlchemy ORM models + Alembic migrations
│   │   └── core/              ← config, auth, logging, middleware
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/               ← Next.js App Router pages
│   │   ├── components/        ← shared UI (shadcn/ui base)
│   │   ├── lib/               ← API clients, utils
│   │   └── types/             ← TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
├── semantic/
│   ├── dbt/                   ← dbt project (models, seeds, metrics)
│   └── cube/                  ← Cube.dev schema files
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── postgres/init.sql
└── docs/
    ├── adr/                   ← Architecture Decision Records
    └── api/                   ← OpenAPI specs
```

---

## 5. Key Commands

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000   # dev server
uv run pytest tests/ -v --tb=short                 # run tests
uv run alembic upgrade head                        # apply migrations
uv run alembic revision --autogenerate -m "msg"    # new migration
uv run ruff check . && uv run ruff format --check . # lint + format

# Frontend
cd frontend
pnpm dev                    # Next.js dev (port 3000)
pnpm build && pnpm start    # production build
pnpm lint                   # ESLint
pnpm typecheck              # tsc --noEmit

# Full stack
docker compose -f infra/docker-compose.dev.yml up -d   # start all services
docker compose down -v                                  # tear down (keeps volumes)
docker compose logs -f backend                          # tail backend logs

# Semantic layer
cd semantic/dbt
dbt run --select +metrics.*   # run dbt models
dbt test                      # run dbt tests
```

---

## 6. Hard Rules — NEVER Violate

### Security & Data Safety
- **NEVER generate destructive SQL** (DROP, DELETE, TRUNCATE) — all DB access is READ-ONLY through the query engine. Insert/update only via explicit service methods.
- **NEVER expose raw connection strings or secrets** in responses, logs, or LLM prompts. Use env vars; reference `settings.py` which loads from `.env`.
- **NEVER pass user-submitted strings directly into SQL**. Always use SQLAlchemy parameterized queries or the query validator.
- **NEVER bypass `ValidationAgent`** before executing generated SQL in production paths.

### LLM & Agent Rules
- **NEVER hardcode model names** in business logic — always reference `settings.LLM_REASONING_MODEL` and `settings.LLM_FAST_MODEL`.
- **NEVER call LLM APIs without timeout + retry logic**. Use the `llm_client.py` wrapper.
- **NEVER store raw user prompts in plaintext DB** without first stripping PII via the sanitizer middleware.
- **Every agent must log**: input tokens, output tokens, latency, model version, and user_id to the `audit_log` table.

### Code Conventions
- **NEVER use `print()` for logging** — use `loguru` logger (`from app.core.logging import logger`).
- **NEVER use `Any` type in Pydantic models** — define explicit schemas.
- **NEVER commit `.env` files** — use `.env.example` with placeholder values only.
- **ALL API routes are versioned** under `/api/v1/` — no bare routes.

---

## 7. Coding Conventions

### Python / Backend
- **Async everywhere**: all FastAPI routes and DB calls are `async def`; use `asyncpg` driver
- **Pydantic v2**: use `model_validator`, `field_validator`, `model_config` — not v1 syntax
- **SQLAlchemy 2.0**: use `select()`, `Session.execute()`, mapped classes — NOT legacy Query API
- **Error handling**: raise `HTTPException` with typed detail dicts `{"code": "...", "message": "..."}`
- **Dependency injection**: auth/session/db via FastAPI `Depends()` — never instantiate in route body
- **File naming**: `snake_case` for Python files, `kebab-case` for frontend files

### TypeScript / Frontend
- **Server components by default** — add `"use client"` only for interactive components
- **All data fetching via** `src/lib/api-client.ts` — never `fetch()` directly in components
- **Zod schemas** for all API response validation in frontend
- **shadcn/ui components** as base — extend with Tailwind, never override base component internals

### Agent & LLM Patterns
- **Prompt templates are versioned files** in `.claude/prompts/` — never inline long prompts in code
- **Few-shot examples** live in `backend/app/agents/examples/` — load dynamically, not hardcoded
- **Schema context compression**: embed only relevant table/column metadata (top-k by cosine similarity from pgvector) — never send full DB schema to LLM
- **Chain of thought**: reasoning models (`claude-opus-4`) always use `thinking` blocks for SQL generation; fast models (`claude-haiku-4`) use direct generation

---

## 8. Database Rules

```sql
-- Every table MUST have:
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
tenant_id   UUID NOT NULL REFERENCES tenants(id)   -- for multi-tenancy

-- RLS policy must exist for every user-data table
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
```

- **NEVER drop columns** — mark as `deprecated_at TIMESTAMPTZ` first, remove after 2 sprint cycles
- **Migrations**: Alembic only — no manual `ALTER TABLE` in psql
- **Indexes**: all foreign keys and `tenant_id` columns must be indexed
- **Query timeout**: all analytical queries are capped at 30s via `SET statement_timeout = '30s'`
- **Apache AGE**: graph queries for data lineage use the `genbi_graph` graph — schema in `backend/app/db/graph_schema.py`

---

## 9. Testing Approach

```
Unit tests:          Pure functions, agent logic, prompt builders, validators
Integration tests:   API routes with test DB, semantic layer queries
E2E tests:           Full NL → SQL → chart → narrative pipeline (slow, marked @pytest.mark.e2e)
LLM eval tests:      Golden dataset of NL/SQL pairs in tests/evals/nl2sql_golden.json
```

- **Always mock LLM calls in unit/integration tests** using `tests/fixtures/llm_mock.py`
- **Golden NL2SQL test suite** must pass before any merge to `main` (20 queries, 90% accuracy threshold)
- **Test DB** is a separate PostgreSQL instance with synthetic data (see `infra/postgres/test_seed.sql`)
- Run: `uv run pytest tests/ -v -m "not e2e"` for fast local feedback

---

## 10. Semantic Layer Rules

- **Metrics are defined ONCE in dbt MetricFlow** — `semantic/dbt/models/metrics/`
- **Cube.dev** exposes those metrics via REST + GraphQL API to agents and frontend
- **NEVER re-implement metric logic** in agent prompts or service code — always query via Cube API
- **Schema catalog** is synchronized to pgvector embeddings nightly via `scripts/embed_schema.py`
- **Column descriptions** are mandatory for all semantic model fields — they are injected into LLM context

---

## 11. Multi-Tenancy & Access Control

- All queries are scoped by `tenant_id` injected from JWT claims
- Row-level security (PostgreSQL RLS) enforces data isolation at DB level
- Column-level masking for PII fields (defined in `backend/app/core/masking.py`)
- Agent prompts include: `"You are operating for tenant {tenant_id} with role {user_role}. Only access data within your authorized scope."`
- Audit log records: `user_id`, `tenant_id`, `query_text`, `generated_sql`, `model_version`, `latency_ms`, `token_count`

---

## 12. Observability & Governance

```python
# Every LLM call must produce an AuditEntry
AuditEntry(
    session_id=...,
    user_id=...,
    tenant_id=...,
    input_prompt_hash=...,   # SHA-256, not raw text
    generated_sql=...,
    model_name=...,
    model_version=...,
    input_tokens=...,
    output_tokens=...,
    latency_ms=...,
    feedback_score=None,     # filled post-hoc
    hallucination_flag=False
)
```

- **Langfuse** is the LLM tracing backend — all traces tagged with `project=genbi`, `env=prod|dev`
- **OpenTelemetry** spans wrap every agent call and DB query
- **Hallucination detection**: if SQL result row count is 0 or diverges >50% from prior similar queries, flag for human review

---

## 13. DO NOT MODIFY (Stable / Protected)

| Path | Reason |
|---|---|
| `backend/app/core/auth.py` | JWT + RBAC logic — changes need security review |
| `backend/app/db/migrations/` | Alembic history — never edit existing migration files |
| `backend/app/agents/validation_agent.py` | SQL safety gate — any relaxation needs explicit approval |
| `semantic/dbt/models/metrics/` | Metric definitions — changes affect downstream Cube API |
| `infra/postgres/init.sql` | DB initialization — destructive if changed incorrectly |

---

## 14. Deployment

```
Dev:     docker compose -f infra/docker-compose.dev.yml up
Staging: GitHub Actions → build Docker images → push to registry → deploy to K8s (staging NS)
Prod:    Manual approval gate in GitHub Actions → K8s (prod NS) rolling update

Required env vars (set in CI secrets / K8s secrets):
  ANTHROPIC_API_KEY
  DATABASE_URL           # asyncpg format: postgresql+asyncpg://...
  REDIS_URL
  CUBE_API_URL
  CUBE_API_SECRET
  LANGFUSE_SECRET_KEY
  LANGFUSE_PUBLIC_KEY
  JWT_SECRET_KEY
  TENANT_ENCRYPTION_KEY

Frontend build: `pnpm build` — outputs to .next/
Backend build: Docker image from backend/Dockerfile
```

---

## 15. Context Pointers

- `@docs/adr/001-semantic-layer-choice.md` — why dbt + Cube over standalone solutions
- `@docs/adr/002-agent-architecture.md` — LangGraph multi-agent topology decision
- `@docs/adr/003-nl2sql-approach.md` — schema embedding strategy and prompt design
- `@backend/app/agents/README.md` — agent registry and inter-agent messaging protocol
- `@semantic/dbt/README.md` — metric taxonomy and naming conventions

---

## 16. Common Tasks

**"Add a new data source connector":**
1. Create `backend/app/connectors/{name}_connector.py` implementing `BaseConnector`
2. Register in `backend/app/connectors/registry.py`
3. Add schema embedding job in `scripts/embed_schema.py`
4. Add connector integration test in `tests/connectors/`
5. Update `.env.example` with new connection string variable

**"Add a new metric":**
1. Define in `semantic/dbt/models/metrics/{domain}.yml` using MetricFlow syntax
2. Run `dbt run --select +metrics.{domain}` + `dbt test`
3. Cube.dev picks up on next sync (or `cd semantic/cube && cube build`)
4. Embed updated schema: `uv run python scripts/embed_schema.py --domain {domain}`

**"Add a new agent":**
1. Create `backend/app/agents/{name}_agent.py` extending `BaseAgent`
2. Register in `backend/app/agents/registry.py` with trigger conditions
3. Add unit tests in `tests/agents/test_{name}_agent.py` with mocked LLM
4. Add golden eval cases to `tests/evals/` if the agent generates SQL or charts
5. Update `RouterAgent` dispatch table in `backend/app/agents/router_agent.py`

**"Debug a hallucinated SQL query":**
1. Pull audit log: `SELECT * FROM audit_log WHERE session_id = '...'`
2. Check Langfuse trace for the session — inspect retrieved schema context
3. Check pgvector similarity scores in `schema_embeddings` table
4. If schema context was wrong, re-run `scripts/embed_schema.py` for affected tables
5. Add the failing NL query to `tests/evals/nl2sql_golden.json` as a regression case

---

## 17. Session Notes

When compacting, always preserve:
- The current migration state (last applied Alembic revision)
- Any failing golden eval queries and their root cause analysis
- Active agent architecture decisions in progress
- Any LLM prompt changes and their eval impact

---
