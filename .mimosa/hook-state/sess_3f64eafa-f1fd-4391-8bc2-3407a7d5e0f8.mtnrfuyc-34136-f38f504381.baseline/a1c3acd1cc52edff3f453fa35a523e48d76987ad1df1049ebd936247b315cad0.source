# GenBI Backend

FastAPI application providing the Generative BI API.

## Architecture

Four-layer design:

```
Interface (FastAPI routes)
  → Orchestration (LangGraph agents: NL2SQL, Chart, Narrative, Router, Validation)
    → Semantic Layer (Cube.dev metrics API + dbt schema catalog)
      → Data Retrieval (SQLAlchemy connectors to PostgreSQL, Snowflake, etc.)
```

## Key Modules

- `app/agents/` — LangGraph agent definitions (NL2SQL, ChartGen, Narrative, Router, Validation)
- `app/agents/chart/` — Flint Chart MCP integration (FlintChartOperator, vis-flint protocol)
- `app/semantic/` — Cube.dev client, schema embedding, metric resolution
- `app/connectors/` — SQLAlchemy database connectors with read-only enforcement
- `app/services/` — Business logic: query execution, chart generation, report assembly
- `app/models/` — Pydantic v2 request/response schemas
- `app/db/` — SQLAlchemy ORM models, Alembic migrations
- `app/core/` — Config, auth, JWT, RBAC, logging, middleware

## Quick Start

```bash
uv run uvicorn app.main:app --reload --port 8000
uv run pytest tests/ -v -m "not e2e"
uv run alembic upgrade head
```
