# GenBI — Generative BI Platform

Natural language → SQL → Chart + Narrative, governed and explainable.

## Quick Start

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && pnpm dev

# Full stack
docker compose -f infra/docker-compose.dev.yml up -d
```

## Architecture

Built on two open-source foundations:

- **[DB-GPT](https://github.com/eosphoros-ai/DB-GPT)** — Agentic AI data application framework (AWEL orchestration, Text2SQL, sandboxed execution, RAG)
- **[Flint Chart](https://github.com/microsoft/flint-chart)** — MCP-native chart rendering (unified spec → Vega-Lite / ECharts / Chart.js, local rendering)

The platform adds a semantic layer (dbt + Cube.dev), multi-tenant governance, and a Next.js 15 frontend on top.

## Project Structure

```
genbi/
├── backend/          FastAPI app + LangGraph agents
├── frontend/         Next.js 15 (App Router) + shadcn/ui
├── semantic/         dbt MetricFlow + Cube.dev schemas
├── infra/            Docker Compose + PostgreSQL init
├── docs/             ADRs and API specs
└── .claude/          Rules, skills, prompt templates
```

## Docs

See `docs/adr/` for architecture decisions and `CLAUDE.md` for the full project context used by AI coding assistants.
