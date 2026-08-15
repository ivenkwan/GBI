# GenBI Platform — Development Documentation

> **Version:** 0.1.0 | **Stack Tier:** Enterprise | **Last updated:** 2026-08-15

A **Generative BI (GenBI) platform** that enables business users to query enterprise data warehouses using natural language, auto-generates visualizations and narrative insights, and delivers governed, explainable analytics at scale.

## Quick Links

### Architecture & Design
- [Architecture Overview](architecture-overview.md) — Four-tier architecture, data flow, technology stack
- [Agent System](agent-system.md) — Multi-agent LangGraph pipeline, agent roster, LLM model usage
- [Architecture Decision Records](adr/) — ADR 001–008 covering chart stack, agent topology, Flint bridge, AGE image, enforced RLS roles, Cube-native catalog, and per-tenant Cube data path

### API
- [API Reference](api-reference.md) — Complete REST API documentation, request/response schemas, SSE streaming

### Backend Services
- [Core Services](core-services.md) — Configuration, logging, LLM client, caching, auth, PII masking, observability
- [Data Layer](data-layer.md) — Database models, connectors (read-only), Apache AGE graph schema, migrations
- [Semantic Layer](semantic-layer.md) — Cube-native metric catalog → Cube.dev API → Python CubeClient

### Frontend
- [Frontend Guide](frontend-guide.md) — Next.js 15 App Router, shadcn/ui components, SSE chat, Explore metric workbench, Zod validators

### Operations
- [Infrastructure](infrastructure.md) — Docker Compose (dev + prod), CI/CD, environment variables, scripts

### Key Concepts

| Concept | Where |
|---|---|
| NL → SQL → Chart → Narrative pipeline | [Agent System](agent-system.md#pipeline-data-flow) |
| Dual chart stack (Flint MCP + AntV G2) | [ADR 001](adr/001-dual-chart-stack.md) |
| Schema embedding + pgvector semantic search | [Semantic Layer](semantic-layer.md) |
| Read-only SQL enforcement (Safety Gate) | [Agent System](agent-system.md#32-validationagent) |
| Dual-tier cache (L1 LRU + L2 Redis) | [Core Services](core-services.md#4-cache-service) |
| Multi-tenant JWT + RLS isolation | [Core Services](core-services.md#5-authentication) |
| SSE streaming from agent pipeline to chat UI | [API Reference](api-reference.md#streaming) |
| Chart hallucination detection + auto-correction | [Agent System](agent-system.md#35-chart-validator) |

### Tech Stack at a Glance

```
Backend:       Python 3.12 · FastAPI · Uvicorn / Gunicorn
LLM Layer:     Anthropic Claude (Opus for SQL, Haiku for speed)
               LangChain / LangGraph orchestration
               LlamaIndex for semantic indexing / RAG
Semantic Layer: Cube.dev (native data models — metric catalog)
Databases:     PostgreSQL 16 · pgvector (embeddings) · Apache AGE (graph lineage)
               Redis (query cache, session state)
Frontend:      Next.js 15 · TypeScript 5.9 · Tailwind CSS v4 · shadcn/ui
Charts:        Flint MCP (static) + AntV G2 (interactive) · Vega-Lite / Altair fallback
Observability: OpenTelemetry · Langfuse · Prometheus + Grafana
CI/CD:         GitHub Actions · Docker + Docker Compose
```
