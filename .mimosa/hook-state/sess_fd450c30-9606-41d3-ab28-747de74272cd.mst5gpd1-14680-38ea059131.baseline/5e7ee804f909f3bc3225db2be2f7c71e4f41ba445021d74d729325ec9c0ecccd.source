# Semantic Layer

> Single source of truth for business metric definitions. Three-tier pipeline: **dbt MetricFlow** → **Cube.dev** → **Python CubeClient**.

## Architecture

```
dbt models (metrics/*.yml)
    │
    v
dbt MetricFlow manifest (target/manifest.json)
    │
    v
Cube.dev (cube.js → semantic_layer_sync)
    │  REST API: /meta, /load
    v
CubeClient (backend/app/semantic/cube_client.py)
    │  Python ↔ LLM context formatting
    v
NL2SQLAgent, NarrativeAgent (agents)
```

---

## dbt Project

**Location:** `semantic/dbt/` | **Project:** `genbi_semantic` v0.1.0

### Materialization Strategy

| Layer | Materialization | Schema |
|---|---|---|
| **staging** | Views | `staging` |
| **metrics** | Tables | `metrics` |
| **marts** | Tables | `marts` |

### Staging Model — `stg_revenue`

**File:** `semantic/dbt/models/staging/stg_revenue.sql`

Transforms raw `transactions` table into business-friendly columns:

```sql
SELECT
    id AS transaction_id,
    customer_id,
    revenue_amount,
    region,
    product_category,
    DATE(created_at) AS transaction_date,
    tenant_id
FROM {{ source('raw', 'transactions') }}
```

### Metric Definitions

**File:** `semantic/dbt/models/metrics/revenue.yml`

#### Revenue Semantic Model

| Entity | Type | Column |
|---|---|---|
| `transaction` | Primary | `transaction_id` |
| `customer` | Foreign | `customer_id` |

| Dimension | Type | Column |
|---|---|---|
| `transaction_date` | Time (daily) | `transaction_date` |
| `region` | Categorical | `region` |
| `product_category` | Categorical | `product_category` |

| Measure | Aggregation | Column |
|---|---|---|
| `revenue_amount` | SUM | `revenue_amount` |
| `transaction_count` | COUNT | — |

#### Metrics

| Metric | Type | Formula |
|---|---|---|
| `revenue_total` | SUM | `SUM(revenue_amount)` |
| `revenue_growth_pct` | DERIVED | `(revenue_total - revenue_prev_period) / revenue_prev_period * 100` |
| `active_users` | COUNT_DISTINCT | `COUNT(DISTINCT user_id)` |
| `conversion_rate` | RATIO | `conversions / total_users` |

### Source Definitions

**File:** `semantic/dbt/models/staging/sources.yml`

Single source `raw` with `transactions` table. Columns: `id`, `customer_id`, `amount`, `region`, `product_category`, `created_at`. Tests: `unique` on `id`, `not_null` on `customer_id`, `amount`, `created_at`.

---

## Cube.js Configuration

**File:** `semantic/cube/cube.js`

```js
module.exports = {
  data_source: process.env.CUBEJS_DB_URL || "postgresql://genbi:genbi@localhost:5432/genbi",
  semantic_layer_sync: {
    dbt: {
      manifest_path: process.env.CUBEJS_DB_MANIFEST_PATH || "../dbt/target/manifest.json",
    },
  },
};
```

**Environment:** `CUBE_API_SECRET` for auth, `CUBEJS_DEV_MODE=true` in development, `CUBEJS_WEB_SOCKETS=true` for live queries.

---

## CubeClient (Python)

**File:** `backend/app/semantic/cube_client.py` | **Singleton:** `get_cube_client()`

### Initialization

```python
client = CubeClient(
    api_url="http://localhost:4000/cubejs-api/v1",
    api_secret="...",
    cache_ttl_seconds=300,
)
```

In-memory caches (`_metric_cache`, `_meta_cache`) + optional Redis cache (lazy-initialized).

### Data Types

```python
class MetricType(enum.Enum):
    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    RATIO = "ratio"
    DERIVED = "derived"
    RUNNING_TOTAL = "running_total"

class DimensionType(enum.Enum):
    STRING = "string"
    NUMBER = "number"
    TIME = "time"
    BOOLEAN = "boolean"
    GEO = "geo"

@dataclass
class MetricDefinition:
    name: str
    title: str
    description: str
    metric_type: MetricType
    cube_name: str
    measure_name: str
    dimensions: list[str]
    time_dimensions: list[str]
    format: str | None
```

### Key Methods

| Method | Returns | Description |
|---|---|---|
| `get_meta(force_refresh=False)` | `CubeMetaResponse` | Fetches `/meta`, parses cubes into `MetricDefinition` objects |
| `list_metrics(force_refresh=False)` | `dict[str, MetricDefinition]` | All metrics keyed by name |
| `get_metric(name)` | `MetricDefinition \| None` | Lookup by name |
| `query(metrics, dimensions, ...)` | `MetricQueryResult` | Executes a Cube `/load` query |
| `format_metrics_for_llm(metrics, names)` | `str` | Markdown-formatted metric catalog for LLM context |
| `format_metric_for_prompt(name, metric)` | `str` | Compact single-metric format |
| `get_agent_context(query, metric_names)` | `str` | **Primary integration point** — returns metric context for NL2SQLAgent |
| `health_check()` | `bool` | Pings `/meta` |

### LLM Context Formatting

`format_metrics_for_llm()` produces:

```markdown
## Available Metrics (from Semantic Layer)

- **revenue_total** (sum)
  Sum of all recognized revenue
  Cube: revenue, Measure: revenue_amount
  Dimensions: region, product_category
  Time dimensions: transaction_date

- **revenue_growth_pct** (derived)
  Period-over-period growth percentage
  ...
```

This is injected into the NL2SQLAgent's context so the LLM understands which metrics exist and how to query them.

### Caching

Dual-layer (Redis + in-memory). TTL: configurable (default 5 min). Keys: `genbi:cube:*`. Serialization handles `MetricDefinition` and `CubeMetaResponse` dataclasses for Redis.

---

## Schema Embeddings

**Script:** `scripts/embed_schema.py`

**Purpose:** Nightly sync of `information_schema` metadata to pgvector for semantic NL2SQL search.

**Process:**
1. Queries `information_schema.tables` + `pg_catalog.pg_description` for table/column metadata with descriptions
2. Groups columns by table, builds a rich text representation per table
3. Generates 1536-dim embeddings via `claude-embeddings-20250219` Anthropic API
4. Upserts into the `schema_embeddings` table (keyed by `tenant_id` + `table_schema` + `table_name`)

**CLI:**
```bash
uv run python scripts/embed_schema.py --schema public --domain revenue --dry-run
uv run python scripts/embed_schema.py --schema public  # full sync
```

---

## Key Principle

> **Metrics are defined ONCE in dbt MetricFlow.** Cube.dev exposes them via REST + GraphQL. The Python `CubeClient` injects them into LLM context. **Never re-implement metric logic** in agent prompts or service code — always query via Cube API.
