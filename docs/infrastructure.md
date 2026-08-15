# Infrastructure

> Docker Compose, CI/CD, environment variables, and utility scripts.

---

## Docker Compose — Development

**File:** `infra/docker-compose.dev.yml`

| Service | Image / Build | Port | Volumes | Notes |
|---|---|---|---|---|
| **postgres** | `pgvector/pgvector:pg16` | `5432` | `postgres_data` (named) + `./postgres/init.sql` mount | `pg_isready` health check, 5s interval |
| **redis** | `redis:7-alpine` | `6379` | None | `redis-cli ping` health check, 5s interval |
| **backend** | Build from `../backend` | `8000` | `../backend:/app` + `flint_data:/tmp/genbi-charts` | Depends on healthy postgres + redis. `uvicorn --reload` hot-reload |
| **frontend** | Build from `../frontend` | `3000` | `../frontend:/app`, `/app/node_modules` (anonymous) | Depends on backend. `pnpm dev` |
| **cube** | `cubejs/cube:latest` | `4000` | None | Cube.dev semantic API |
| **prometheus** | `prom/prometheus:latest` | `9090` | `./prometheus/prometheus.yml` mount | |
| **grafana** | `grafana/grafana:latest` | `3001` | None | Depends on prometheus |
| **otel_collector** | `otel/opentelemetry-collector-contrib:latest` | `4318` (HTTP), `8888` (metrics) | None | |

### Key differences from production:
- Hot-reload: `uvicorn --reload` (backend), `pnpm dev` (frontend)
- Volume mounts for live code editing
- Health check dependencies between services
- Additional observability services (Prometheus, Grafana, OTel Collector)

---

## Docker Compose — Production

**File:** `infra/docker-compose.yml`

| Service | Image / Build | Port | Volumes | Restart |
|---|---|---|---|---|
| **postgres** | `pgvector/pgvector:pg16` | `5432` | `postgres_data` + `init.sql` | `unless-stopped` |
| **redis** | `redis:7-alpine` | `6379` | None | `unless-stopped` |
| **backend** | Build from `../backend` | `8000` | None | `unless-stopped` |
| **frontend** | Build from `../frontend` (target: `production`) | `3000` | None | `unless-stopped` |

- Backend CMD: `gunicorn` with 4 `uvicorn` workers
- Frontend env: `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000/api/v1`
- Credentials from `../backend/.env`

### Start Commands

```bash
# Development
docker compose -f infra/docker-compose.dev.yml up -d

# Production
docker compose -f infra/docker-compose.yml up -d

# Tear down (keep volumes)
docker compose down

# Tear down (remove volumes)
docker compose down -v

# Tail logs
docker compose logs -f backend
```

---

## PostgreSQL Initialization

**File:** `infra/postgres/init.sql`

### Extensions
- `pgcrypto` — UUID generation (`gen_random_uuid()`)
- `vector` — pgvector for embedding storage (1536-dim)
- `age` — Apache AGE for graph queries (lineage, impact analysis)

### Schema Tables

| Table | Purpose | Key columns |
|---|---|---|
| `tenants` | Multi-tenant root | `id UUID PK`, `name VARCHAR(255) UNIQUE`, `created_at`, `updated_at` |
| `users` | Per-tenant users | `id UUID PK`, `tenant_id FK`, `email UNIQUE`, `hashed_password`, `roles JSONB` |
| `audit_log` | NL2SQL audit trail | `session_id`, `user_id`, `tenant_id`, `input_prompt_hash`, `generated_sql`, `model_name`, `token_count`, `latency_ms` |
| `conversations` | Chat sessions | `id UUID PK`, `user_id`, `tenant_id`, `title` |
| `schema_embeddings` | Vector store | `table_schema`, `table_name`, `embedding VECTOR(1536)`, `description` |
| `agent_examples` | Few-shot storage | `agent_name`, `input_text`, `output_json`, `embedding VECTOR(1536)` |

### Indexes
- `schema_embeddings` table: IVFFlat index on `vector_cosine_ops` for semantic similarity search
- `audit_log`: indexed by `session_id`, `tenant_id`, `created_at`
- `agent_examples`: indexed by `agent_name` + IVFFlat
- All FKs and `tenant_id` columns indexed

---

## Prometheus Configuration

**File:** `infra/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "genbi-backend"
    static_configs:
      - targets: ["backend:8000"]
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
```

---

## CI/CD Pipeline

**File:** `.github/workflows/ci.yml`

**Triggers:** Push to `main`/`develop`, PR to `main`

### Jobs

#### 1. Backend — Lint & Test (parallel with frontend)
- Python 3.12, `uv`
- PostgreSQL + Redis service containers
- Steps: checkout → `uv sync --frozen` → ruff lint + format check → alembic migrations check → pytest (non-e2e, with coverage) → golden NL2SQL eval → upload coverage to Codecov

#### 2. Frontend — Lint & Build (parallel with backend)
- Node 20, `pnpm` 9
- Steps: checkout → `pnpm install` → `tsc --noEmit` → lint → build

#### 3. Docker — Build Images (sequential, only on push to main/develop)
- Docker Buildx, GHCR login
- Build + push backend and frontend images tagged `:sha` and `:latest`
- GitHub Actions cache for Docker layers

#### 4. Golden Eval Gate (on main branch only)
- PostgreSQL service container
- Runs golden NL2SQL eval suite
- Blocks merges below **90% accuracy threshold**

---

## Environment Variables

**File:** `.env.example`

| Category | Variable | Default |
|---|---|---|
| **LLM** | `ANTHROPIC_API_KEY` | (required) |
| | `LLM_REASONING_MODEL` | `claude-opus-4` |
| | `LLM_FAST_MODEL` | `claude-haiku-4` |
| **Database** | `DATABASE_URL` | `postgresql+asyncpg://genbi_app:genbi_app@localhost:5432/genbi` (RLS-bound runtime role) |
| | `DATABASE_URL_AUTH` | (optional) `postgresql+asyncpg://genbi_auth:genbi_auth@…` — login-only role; derived from `DATABASE_URL` if unset |
| | `DATABASE_URL_SYNC` | `postgresql://genbi:genbi@localhost:5432/genbi` (owner — Alembic + admin scripts only) |
| **Redis** | `REDIS_URL` | `redis://localhost:6379/0` |
| **Semantic** | `CUBE_API_URL` | `http://localhost:4000/cubejs-api/v1` |
| | `CUBE_API_SECRET` | (required) |
| **Observability** | `LANGFUSE_SECRET_KEY` | |
| | `LANGFUSE_PUBLIC_KEY` | |
| | `LANGFUSE_HOST` | `https://cloud.langfuse.com` |
| | `OTEL_EXPORTER_OTLP_ENDPOINT` | |
| **Auth** | `JWT_SECRET_KEY` | `change-me` (override in production!) |
| | `JWT_ALGORITHM` | `HS256` |
| | `JWT_EXPIRE_MINUTES` | `60` |
| **Tenant** | `TENANT_ENCRYPTION_KEY` | |
| **Flint** | `FLINT_MCP_BACKENDS` | `vegalite,echarts,chartjs` |
| | `FLINT_MCP_DATA_ROOTS` | `/tmp/genbi-charts` |
| **App** | `APP_ENV` | `development` |
| | `DEBUG` | `True` |
| | `LOG_LEVEL` | `DEBUG` |
| | `CORS_ORIGINS` | `["http://localhost:3000"]` |

---

## Dockerfiles

### Backend (`backend/Dockerfile`)
```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# Install deps, copy code, expose 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend (`frontend/Dockerfile`)
Three-stage build:
1. **deps** (`node:22-alpine`) — `pnpm install`
2. **builder** — `pnpm build`
3. **production** — copy `.next/standalone` + `.next/static` + `public`, expose 3000, run `node server.js`

---

## Utility Scripts

### `scripts/embed_schema.py`
Nightly schema embedding sync for pgvector semantic search.

```bash
uv run python scripts/embed_schema.py --schema public            # Full sync
uv run python scripts/embed_schema.py --domain revenue --dry-run # Preview only
```

- Queries `information_schema` + `pg_catalog.pg_description`
- Generates 1536-dim embeddings via `claude-embeddings-20250219`
- Upserts into `schema_embeddings` table
- Returns `{tables_processed, embeddings_generated, errors}`

### `scripts/seed_test_data.py`
Synthetic test data generator for development.

```bash
uv run python scripts/seed_test_data.py                          # Default (1 tenant)
uv run python scripts/seed_test_data.py --tenants 3 --clear      # 3 tenants, fresh start
```

Generates realistic data for 10 tables:
`sales`, `customers`, `orders`, `transactions`, `users`, `products`, `regions`, `sales_representatives`, `deals`, `activity`

Each table has a dedicated generator function (realistic company names, product names, dates). Batch inserts in chunks of 100 with `ON CONFLICT DO NOTHING`.

---

## Key Commands

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000   # Dev server
uv run pytest tests/ -v --tb=short                 # Fast tests (skip e2e)
uv run pytest tests/ -v -m "not e2e"               # Skip E2E
uv run alembic upgrade head                        # Apply migrations
uv run alembic revision --autogenerate -m "msg"    # New migration
uv run ruff check . && uv run ruff format --check . # Lint + format

# Frontend
cd frontend
pnpm dev                    # Next.js dev (port 3000)
pnpm build && pnpm start    # Production
pnpm lint                   # ESLint
pnpm typecheck              # tsc --noEmit

# Semantic layer
cd semantic/dbt
dbt run --select +metrics.*   # Run dbt models
dbt test                      # Run dbt tests
```
