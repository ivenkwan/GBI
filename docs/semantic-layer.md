# Semantic Layer

> Single source of truth for business metric definitions:
> **Cube-native data models** (`semantic/cube/model/`) served by **Cube.dev**,
> consumed by the Python **CubeClient**. See
> [ADR 007](adr/007-cube-native-semantic-layer.md) for why the dbt tier was
> dropped.

## Architecture

```
semantic/cube/model/*.yml   (10 cubes, 23 measures — the catalog)
    │
    v
Cube.dev (cube.js, CUBEJS_DB_* env, cube_reader role)
    │  REST API: /meta (definitions), /load (data — Phase 10)
    v
CubeClient (backend/app/semantic/cube_client.py, JWT-authenticated)
    │  /meta → MetricDefinition map → LLM context formatting
    v
ChatService → NL2SQLAgent prompt ("## Available Metrics") + /api/v1/metrics/list
```

## The Catalog

**Location:** `semantic/cube/model/` — one YAML per cube, over the ten
seeded analytics tables. Highlights:

| Cube | Measures | Dimensions (non-time) |
|---|---|---|
| Sales | `revenue_total` (USD), `units_sold`, `avg_revenue_per_sale`, `sale_count` | region, product_name |
| Orders | `order_count`, `order_value` (USD), `avg_order_value` | status |
| Customers | `customer_count`, `active_customers` (status filter) | country, status |
| Transactions | `transaction_volume` (USD), `transaction_count`, `avg_transaction` | type, status |
| WebUsers | `user_count`, `active_users` | country, status |
| Activity | `event_count`, `unique_active_users` (countDistinct) | event_type |
| Deals | `pipeline_value` (USD), `deal_count`, `won_deals`, `win_rate` (calculated, %) | stage |
| SalesReps | `rep_count` | name |
| Products | `product_count`, `avg_price` | product_name, category |
| Regions | `region_count` | region_name |

Rules enforced by `backend/tests/semantic/test_catalog.py`:

- unique cube names and measure names across the catalog
- joins reference existing cubes and are **symmetric** (both sides declared)
- every cube carries a `tenant_id` dimension (hidden; Phase-10 queryRewrite hook)
- every measure has a `type` or a `sql` expression
- the core metrics (revenue, orders, active users, pipeline, win rate...) exist

**Joins follow real seed foreign keys only**: Orders↔Customers,
Deals↔SalesReps↔Regions, Activity↔WebUsers. `sales.product_id`/`rep_id` are
dangling in the seed data, so Sales declares no joins.

## Cube Runtime

- **Config:** `semantic/cube/cube.js` — API secret + dev mode from env.
- **Database:** standard `CUBEJS_DB_HOST/PORT/NAME/USER/PASS` env; Cube
  connects as the read-only `cube_reader` role (created by
  `infra/postgres/init.sql`).
- **Dev compose:** the `cube` service mounts `semantic/cube` at `/cube/conf`
  and healthchecks via `node -e fetch(...)`.
- **Secrets:** `scripts/gen-env.sh` writes `semantic/cube/.env`, keeping
  `CUBEJS_API_SECRET` aligned with the backend's `CUBE_API_SECRET`.

### RLS interaction (important)

Analytics tables are FORCE-RLS tenant-scoped (Phase 8b / ADR 006), and data
queries are tenant-correct since Phase 10 (ADR 008): the backend mints JWTs
carrying a `tenantId` claim; Cube keys orchestrators (driver pools) by
tenant; each pool's connections set `app.current_tenant_id` via the pg
`options` parameter — the GUC the RLS policies consume. **Postgres remains
the enforcement layer**: if any link is misconfigured, queries return zero
rows (fail-closed), never another tenant's data. `POST /api/v1/metrics/query`
and the Explore page use this path; metadata (`/meta`) needs no tenant.

## CubeClient

**Location:** `backend/app/semantic/cube_client.py`

- **Auth:** HS256 JWT signed with `CUBE_API_SECRET` (cached ~1h). Data
  queries add a `tenantId` claim — cached per tenant — which Cube surfaces
  as `securityContext` (ADR 008).
- **`get_meta()`**: fetches/parse `/meta` → `CubeMetaResponse{cubes,
  metrics, raw}`. The **raw payload** is what gets cached (Redis + in-memory,
  TTL 5 min) and re-parsed on hit — serializing the parsed form loses the
  metrics map.
- **`list_metrics()` / `get_metric(name)`**: MetricDefinition lookup, indexed
  both as `cube.measure` and bare `measure`.
- **`query(..., tenant_id=...)`**: POST `/load` with measures/dimensions/timeDimensions/
  filters — tenant-scoped through the per-tenant driver GUC; results cached
  per tenant in the two-tier cache (300s).
- **`get_agent_context(query=...)`**: the primary agent integration point.
  With ≤20 metrics, formats the full catalog; above that, keyword-ranks
  metrics against the query (name 3×, title/cube 2×, description 1×) and
  injects the top 20; no keyword overlap falls back to the full list.
- **`health_check()`**: returns bool, never raises.
- Failure semantics: callers fail open — ChatService continues without
  metric context when Cube is down.

### MetricDefinition

```python
name            # "Sales.revenue_total"
title           # "Total Revenue"
description     # human + LLM readable
metric_type     # MetricType (sum/count/count_distinct/avg/min/max/...)
cube_name       # "Sales"
measure_name    # "revenue_total"
dimensions      # non-time dimension names
time_dimensions # time dimension names
format          # {"currency": "USD"} | {"percent": ...} | None
```

## API Surface

- `GET /api/v1/metrics/list` — the catalog as JSON (JWT-authenticated;
  `503 {"detail": {"code": "CUBE_UNAVAILABLE"}}` when Cube is down).
- `POST /api/v1/metrics/query` — tenant-scoped metric query (ADR 008);
  measures validated against the catalog (`400 INVALID_METRIC`); results
  cached 300s per tenant.
- `GET /api/v1/datasources` — the cubes as datasource summaries.
- Frontend: the `/explore` page (catalog → query builder → table + chart).

## Key Principle

Metrics are defined ONCE in `semantic/cube/model/`. Never re-implement
metric logic in agent prompts or service code — always consume via
CubeClient.

## Adding a Metric

1. Edit the cube YAML (or add a cube file).
2. `uv run pytest tests/semantic/test_catalog.py` — invariants must hold.
3. `make restart` — `/meta` reflects the change (5-min client cache).
