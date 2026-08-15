# GenBI Semantic Layer

This directory contains the semantic layer configuration for GenBI:

- **dbt/**: dbt Core project with MetricFlow metric definitions
- **cube/**: Cube.dev schema files exposing metrics via REST + GraphQL

## Architecture

```
dbt (source of truth for metrics)
  → dbt build compiles models and materializes metric definitions
    → Cube.dev imports dbt manifest and exposes metrics via API
      → GenBI backend queries Cube API for metric resolution
        → Agents use metric definitions in NL2SQL prompts
```

## Metric Naming Convention

`{domain}.{metric_name}` — e.g. `revenue.total`, `users.active_daily`

## Getting Started

```bash
# dbt
cd semantic/dbt
dbt deps
dbt run
dbt test

# Cube
cd semantic/cube
cp .env.example .env  # set CUBEJS_DB_URL and CUBEJS_DBT_MANIFEST_PATH
npm install
npm run dev            # Cube Developer Playground at http://localhost:4000
```
