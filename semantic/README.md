# Semantic Layer

> **Source of truth: Cube-native data models** (`semantic/cube/schema/*.yml`).
> See [ADR 007](../docs/adr/007-cube-native-semantic-layer.md) for why the
> dbt MetricFlow scaffold was removed.

## What lives here

```
semantic/cube/
├── cube.js          ← Cube project config (API secret, dev mode)
├── .env.example     ← CUBEJS_DB_* (cube_reader role) + API secret template
└── schema/          ← THE CATALOG — one YAML per cube over the seeded
                       analytics tables (10 cubes, 23 measures)
    ├── sales.yml        revenue_total, units_sold, avg_revenue_per_sale, sale_count
    ├── orders.yml       order_count, order_value, avg_order_value (joins Customers)
    ├── customers.yml    customer_count, active_customers
    ├── transactions.yml transaction_volume, transaction_count, avg_transaction
    ├── web_users.yml    user_count, active_users (joins Activity)
    ├── activity.yml     event_count, unique_active_users (joins WebUsers)
    ├── deals.yml        pipeline_value, deal_count, won_deals, win_rate
    ├── sales_reps.yml   rep_count (joins Deals, Regions)
    ├── products.yml     product_count, avg_price
    └── regions.yml      region_count (joins Deals, SalesReps)
```

## Principles

1. **Metrics are defined ONCE here.** Never re-implement metric logic in
   agent prompts or service code — the backend consumes them via
   `CubeClient` (`/meta` for definitions, `/load` for data).
2. **Every cube carries `tenant_id`** as a (hidden) dimension — the hook for
   per-tenant query rewriting when data queries land (Phase 10).
3. **Joins follow real foreign keys only.** `sales.product_id`/`rep_id` are
   dangling in the seed data, so Sales deliberately declares no joins.
4. **Structural tests guard the catalog** (`backend/tests/semantic/test_catalog.py`):
   unique names, symmetric joins, tenant dimension, core metrics present.

## Runtime

- The `cube` service (dev compose) mounts this directory at `/cube/conf`
  and connects to Postgres as the read-only `cube_reader` role.
- `scripts/gen-env.sh` writes `semantic/cube/.env` with the compose-network
  host and the shared `CUBEJS_API_SECRET` (aligned with the backend).
- Metric metadata (`/meta`) powers the NL2SQL agent's metric context and
  `GET /api/v1/metrics/list`. Data queries (`/metrics/query`) are Phase 10:
  analytics tables are RLS-enforced, so Cube needs per-tenant GUC driver
  work first (see ADR 006/007).

## Adding a metric

1. Edit the cube YAML in `schema/` (add a measure, or a new cube file for a
   new table).
2. Run `uv run pytest tests/semantic/test_catalog.py` — structural invariants
   must hold.
3. Restart the cube service (`make restart`); `/meta` reflects the change
   (CubeClient caches for 5 min).
