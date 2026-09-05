# Architecture Overview

> See also: [ADR 002: Multi-Agent Architecture](adr/002-agent-architecture.md) | [ADR 001: Dual Chart Stack](adr/001-dual-chart-stack.md)

## Four-Tier Architecture

```
┌─────────────────────────────────────────────┐
│  Layer 1: Interface                         │
│  Next.js 15 App Router · shadcn/ui · SSE    │
├─────────────────────────────────────────────┤
│  Layer 2: Orchestration (LangGraph Agents)  │
│   ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│   │ NL2SQL   │ │ ChartGen │ │ Narrative  │ │
│   │ Agent    │ │ Agent    │ │ Agent      │ │
│   └──────────┘ └──────────┘ └────────────┘ │
├─────────────────────────────────────────────┤
│  Layer 3: Semantic Layer                    │
│  dbt MetricFlow → Cube.dev → CubeClient    │
├─────────────────────────────────────────────┤
│  Layer 4: Data Retrieval                    │
│  PostgreSQL · pgvector · Apache AGE         │
├─────────────────────────────────────────────┤
│  Layer 5: Governance & Audit                │
│  AuditLog · Langfuse · Prompt logs          │
└─────────────────────────────────────────────┘
```

## Layer 1 — Interface

- **Framework:** Next.js 15 App Router, React 19, TypeScript 5.9
- **Styling:** Tailwind CSS v4 with a custom `brand` palette, shadcn/ui component primitives
- **Streaming:** SSE (`text/event-stream`) from backend agent pipeline to chat UI
- **Auth:** JWT-based with `AuthProvider` + `AuthGuard` wrapping the chat interface
- **Charts:** Rendered as SVG (inline `dangerouslySetInnerHTML`) or base64 PNG from Flint/Altair bridge

See: [Frontend Guide](frontend-guide.md)

## Layer 2 — Orchestration

Six specialized agents orchestrated by LangGraph, inspired by DB-GPT's AWEL patterns:

| Agent | Input | Output | Model |
|---|---|---|---|
| `RouterAgent` | User query | Intent + dispatch plan | Haiku-4 |
| `NL2SQLAgent` | Query + schema context + metrics | SQL + explanation + table list | Opus-4 (thinking) |
| `ValidationAgent` | Generated SQL | Safety verdict + validated SQL | Deterministic |
| `ChartGenAgent` | Result set + intent | Flint ChartAssemblyInput spec + rendered image | Haiku-4 |
| `NarrativeAgent` | Data summary + chart context | 3-5 sentence insight paragraph | Haiku-4 |
| `ChartValidator` | Chart spec + data | Validation issues + corrected spec | Deterministic |

The pipeline is conditionally routed: not every query needs all agents. The `RouterAgent` classifies intent (`chat_data`, `chat_visualize`, `chat_report`, `chat_knowledge`, `chat_explore`) and the orchestrator skips irrelevant stages.

See: [Agent System](agent-system.md)

## Layer 3 — Semantic Layer

Three-tier pipeline ensuring metrics are defined once and consumed everywhere:

1. **dbt MetricFlow** (`semantic/dbt/`) — Source-of-truth metric definitions, staging models, dimension/measure/entity specifications
2. **Cube.dev** (`semantic/cube/`) — REST + GraphQL API exposing those metrics to agents and frontend
3. **CubeClient** (`backend/app/semantic/`) — Async Python client with metric-to-LLM formatting

Column descriptions from dbt `schema.yml` are injected into LLM context. Schema embeddings are synced to pgvector nightly via `scripts/embed_schema.py`.

See: [Semantic Layer](semantic-layer.md)

## Layer 4 — Data Retrieval

- **Primary store:** PostgreSQL 16 with extensions: `pgvector` (schema embeddings, semantic search), `apache_age` (graph queries for lineage/impact analysis)
- **Connectors:** `BaseConnector` → `PostgreSQLConnector` (read-only). All queries are read-only, capped at 30s via `SET LOCAL statement_timeout`, and injected with `SET TRANSACTION READ ONLY`
- **Cache:** Dual-tier — L1 (in-memory LRU, 1000 entries) + L2 (Redis, shared across instances)
- **Session:** Async SQLAlchemy with `asyncpg` driver

See: [Data Layer](data-layer.md) | [Core Services](core-services.md#4-cache-service)

## Layer 5 — Governance & Audit

Every LLM call produces an `AuditLog` entry: session_id, user_id, tenant_id, hashed prompt, generated SQL, model name/version, token counts, latency. Langfuse provides LLM tracing. OpenTelemetry spans wrap agent calls and DB queries. Prometheus metrics export via `/metrics`.

## Data Flow (Full Pipeline)

```
User Query (ChatView)
  → POST /api/v1/chat/stream (SSE)
    → ChatService.process_query_stream()
      ├─ RouterAgent        → intent: "chat_data"
      ├─ CubeClient         → metric definitions for LLM context
      ├─ NL2SQLAgent        → SQL (Opus-4, thinking, temp=0)
      ├─ ValidationAgent    → safety check (deterministic)
      ├─ PostgreSQLConnector → read-only execution (30s timeout)
      ├─ ChartGenAgent      → ChartAssemblyInput + Flint/Altair render (Haiku-4)
      ├─ ChartValidator     → hallucination detection + auto-correct
      └─ NarrativeAgent     → insight text (Haiku-4, temp=0.3)
  → SSE events: intent → sql → validation → data → chart → narrative → done
  → ChatView renders incrementally (stage badges, SQL block, chart card, narrative)
```

## Multi-Tenancy Model

> Design authority: [ADR 006](adr/006-enforced-rls-roles.md) (enforced RLS roles),
> [ADR 008](adr/008-per-tenant-cube-data-path.md) (per-tenant Cube data path),
> [ADR 009](adr/009-platform-admin-plane.md) (admin plane — **planned, Phases 21–22**),
> [ADR 010](adr/010-tenant-knowledge-base.md) (tenant knowledge base — **planned, Phase 24**),
> [ADR 011](adr/011-tenant-byok-llm.md) (tenant BYOK LLM — **planned, Phases 25–26**).

The platform separates a **data plane** (per-tenant analytical workloads) from
a **control plane** (tenant lifecycle, identity, platform administration):

```
                    ┌──────────────────────────────────────────┐
                    │  Control plane (ADR 009 — planned)       │
                    │  /admin portal · platform_admins grants  │
                    │  tenant lifecycle · genbi_admin role     │
                    │  admin_audit · BYOK provider config      │
                    │  (ADR 011 — planned)                     │
                    └───────────────┬──────────────────────────┘
                                    │ provisions / suspends / configures
┌────────────────────────────────────▼─────────────────────────────────────┐
│  Data plane (per tenant, enforced)                                       │
│  JWT (sub, tenant_id, roles[, platform_admin])                           │
│    ├─ RLS: FORCE tenant_isolation on app.current_tenant_id GUC           │
│    ├─ Roles: genbi_app (runtime) · genbi_auth (login)                    │
│    │         genbi_admin (control plane, planned) · genbi (owner, DDL)   │
│    ├─ LLM calls: per-tenant BYOK resolution (ADR 011 — planned) —        │
│    │   Anthropic-native or OpenAI-format endpoints with tenant-held      │
│    │   keys (pgcrypto at rest); platform key only when no tenant config  │
│    ├─ Cube: per-tenant orchestrators via tenantId claim → driver GUC     │
│    ├─ Tenant knowledge base (ADR 010 — planned): wiki pages +            │
│    │   pgvector chunks feeding NL2SQL context                           │
│    └─ Governance: audit_log per LLM call (provider + key_source,         │
│        planned) · AGE lineage per artifact                              │
└──────────────────────────────────────────────────────────────────────────┘
```

Two scopes of authority, two mechanisms: **tenant roles** (`users.roles`
JSONB — `user`, `admin`) govern in-tenant capabilities; **platform
superusers** are a separate grant table (`platform_admins`) checked by a
dedicated dependency — never a string in the tenant roles array (ADR 009 §1).
Tenant suspension and superuser revocation are enforced via short-TTL cached
status checks, not just at login.

## Project Structure

```
genbi/
├── backend/
│   ├── app/
│   │   ├── agents/        ← LangGraph agent definitions
│   │   │   ├── chart/     ← Flint bridge, AWEL operator, vis-flint protocol
│   │   │   ├── narrative/
│   │   │   ├── nl2sql/
│   │   │   └── validation/ ← SQL safety gate + chart validator
│   │   ├── api/v1/        ← FastAPI routers (versioned)
│   │   ├── connectors/    ← SQLAlchemy DB connectors (read-only)
│   │   ├── core/          ← config, auth, cache, llm_client, masking, observability
│   │   ├── db/            ← ORM models, session, graph schema, migrations
│   │   ├── models/        ← Pydantic schemas (chat, chart)
│   │   ├── semantic/      ← CubeClient (metrics API)
│   │   └── services/      ← ChatService (pipeline orchestrator)
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/           ← Next.js App Router pages
│       │   └── admin/     ← Platform admin portal (planned — ADR 009)
│       ├── components/    ← shadcn/ui + chat + auth + charts (+ admin, wiki: planned)
│       ├── lib/           ← api-client, validators (Zod), shadcn utils
│       └── types/         ← TypeScript interfaces
├── semantic/
│   ├── dbt/               ← MetricFlow metrics + staging models
│   └── cube/              ← Cube.dev schema
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── postgres/init.sql
├── docs/                  ← documentation (you are here)
│   └── adr/               ← Architecture Decision Records
└── scripts/               ← embed_schema.py, seed_test_data.py
```

## Key Design Decisions

| Decision | ADR | Rationale |
|---|---|---|
| Multi-agent over monolithic | [002](adr/002-agent-architecture.md) | Specialized prompts, per-stage model selection, independent testing |
| LangGraph over raw chains | [002](adr/002-agent-architecture.md) | Conditional routing, checkpointing, per-agent streaming |
| Flint MCP + AntV G2 dual stack | [001](adr/001-dual-chart-stack.md) | Flint for static export, G2 for interactive dashboards |
| Vega-Lite (Altair) fallback | [004](adr/004-flint-bridge-fallback.md) | Ship without Flint dependency; same schema regardless of renderer |
| Deterministic safety gates | N/A | SQL validation and chart validation use pure rules — zero LLM calls, zero hallucination risk |
| Correction over rejection | N/A | Chart validator prefers fuzzy-match fix + chart-type downgrade over failing the request |
| Read-only by default | N/A | All connectors enforce read-only; writes require explicit service methods with auth |
| Control/data plane split | [009](adr/009-platform-admin-plane.md) | Platform administration is a separate grant scope + DB role; tenant roles stay tenant-scoped |
| Least-privilege DB roles per purpose | [006](adr/006-enforced-rls-roles.md), [009](adr/009-platform-admin-plane.md) | genbi_app / genbi_auth / genbi_admin each get one job; owner role for migrations only |
| Tenant knowledge as agent context | [010](adr/010-tenant-knowledge-base.md) | Wiki lives inside the tenant RLS boundary and feeds NL2SQL retrieval — not an external doc dump |
| Per-tenant BYOK LLM providers | [011](adr/011-tenant-byok-llm.md) | One resolution layer inside the central client; Anthropic-native + OpenAI-format adapters; tenant keys pgcrypto-encrypted, never echoed; no silent fallback to the platform key |
