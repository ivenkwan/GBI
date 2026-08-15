# Data Layer

> ORM models, database sessions, connectors, Apache AGE graph schema, and migrations.

---

## ORM Models

**File:** `backend/app/db/models.py`

### `Base` — SQLAlchemy `DeclarativeBase`

### `Tenant` (table: `tenants`)

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK, `uuid4()` default |
| `name` | `String(255)` | Unique, not null |
| `created_at` | `TIMESTAMPTZ` | `utcnow()` default |
| `updated_at` | `TIMESTAMPTZ` | `utcnow()` default, onupdate |

### `AuditLog` (table: `audit_log`)

Every LLM call writes an entry. Schema:

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `session_id` | `UUID` | Indexed, not null |
| `user_id` | `UUID` | Not null |
| `tenant_id` | `UUID` | FK → tenants, indexed |
| `input_prompt_hash` | `String(64)` | SHA-256 of prompt (not raw text) |
| `generated_sql` | `Text` | Nullable |
| `model_name` | `String(100)` | e.g. `claude-opus-4` |
| `model_version` | `String(50)` | Model version string |
| `input_tokens` | `Integer` | Default 0 |
| `output_tokens` | `Integer` | Default 0 |
| `latency_ms` | `Float` | Default 0.0 |
| `feedback_score` | `Integer` | Nullable, filled post-hoc |
| `hallucination_flag` | `Boolean` | Default False |
| `created_at` | `TIMESTAMPTZ` | |

### `Conversation` (table: `conversations`)

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | Not null |
| `tenant_id` | `UUID` | FK → tenants, indexed |
| `title` | `String(500)` | Nullable |
| `created_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |

---

## Database Session

**File:** `backend/app/db/session.py`

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### `get_db()` — FastAPI Dependency

```python
async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.commit()
```

---

## Connectors

### `BaseConnector` (ABC)

**File:** `backend/app/connectors/base.py`

```python
class BaseConnector(ABC):
    name: str = "base"
    _read_only: bool = True     # All connectors enforce read-only

    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def execute(self, sql: str) -> list[dict]: ...
    @abstractmethod
    async def get_schema(self) -> dict: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
```

Every connector is read-only by design. Writes require explicit service methods with authorization.

### `PostgreSQLConnector`

**File:** `backend/app/connectors/postgresql_connector.py` | **Name:** `"postgresql"`

**Constructor:**
```python
PostgreSQLConnector(
    connection_url=settings.DATABASE_URL,
    schema="public",
    pool_size=10,
    max_overflow=5,
    echo=False,
)
```

**`execute(sql, params=None) → list[dict]`:**
1. Requires `_connected = True`
2. Rejects non-SELECT queries: validates SQL starts with `SELECT`, `WITH`, `EXPLAIN`, `SHOW`, or `DESCRIBE`
3. Prepends `SET LOCAL statement_timeout = '30s'; SET LOCAL default_transaction_read_only = on;`
4. Executes inside `SET TRANSACTION READ ONLY` block
5. Converts rows to dicts; types converted with `isoformat()` for JSON serialization

**`get_schema() → dict`:**
Queries `information_schema.tables` + `information_schema.columns` for the configured schema. Includes table/column comments (`obj_description`, `col_description`) and approximate row counts.

**`explain(sql) → dict`:**
Runs `EXPLAIN (FORMAT JSON)` and extracts `estimated_cost` and `estimated_rows`.

**`get_sample_rows(table_name, schema, limit=5) → list[dict]`:**
Uses quoted identifiers for read-only sampling.

### Connector Registry

**File:** `backend/app/connectors/registry.py`

```python
_registry: dict[str, type[BaseConnector]] = {}

def register_connector(name: str): ...  # decorator
def get_connector(name: str) -> type[BaseConnector] | None: ...
def list_connectors() -> list[str]: ...
```

---

## Schema Retrieval (NL2SQL grounding, Phase 11)

**File:** `backend/app/services/schema_retrieval.py` | **Provider:** `backend/app/core/embeddings.py`

The user's query is embedded (OpenAI `text-embedding-3-small`, 1536 dims —
matching the `VECTOR(1536)` columns) and matched against the tenant-scoped
`schema_embeddings` (top-k tables) and `agent_examples` (top-k validated
NL/SQL pairs) tables via cosine distance (`<=>`). Reads run through
`PostgreSQLConnector` as the RLS-bound `genbi_app` role with the tenant GUC
set, so retrieval is tenant-isolated at the database layer.

Wired in `ChatService._step_nl2sql` with the two-tier cache
(`schema:{query_hash}` TTL 86400s, `fewshot:{query_hash}` TTL 3600s) and
everything fails open — no key / no embeddings / DB down → empty context.
Populate with `PYTHONPATH=backend uv run python scripts/embed_schema.py
--examples` (embeds all tables + the 20 golden NL/SQL pairs; needs
`OPENAI_API_KEY`; invalidates the schema cache after sync).

---

## Apache AGE Graph Schema

**File:** `backend/app/db/graph_schema.py` | **Graph name:** `genbi_graph`

### Vertex Labels

| Label | Description |
|---|---|
| `TABLE` | Database table or Cube cube |
| `COLUMN` | Table column or Cube dimension |
| `METRIC` | Business metric (Cube measure) |
| `DASHBOARD` | User-created dashboard |
| `USER` | Platform user (for access control edges) |

### Edge Labels

| Label | Direction | Description |
|---|---|---|
| `TABLE_CONTAINS` | TABLE → COLUMN | Table columns |
| `METRIC_SOURCE` | METRIC → TABLE | Which table a metric derives from |
| `METRIC_DEPENDS` | METRIC → METRIC | Derived metric dependency chain |
| `DASHBOARD_USES` | DASHBOARD → METRIC/TABLE | Dashboard data sources |
| `USER_CAN_ACCESS` | USER → TABLE/METRIC | Row-level access control |
| `TABLE_JOINS` | TABLE → TABLE | Known join paths between tables |

### Key Functions

| Function | Purpose |
|---|---|
| `init_age_graph(db_session)` | Idempotent: creates AGE extension + graph |
| `ingest_table(db_session, ...)` | Creates Table + Column vertices with edges |
| `ingest_metric(db_session, ...)` | Creates Metric vertices linked to tables |
| `get_metric_lineage(db_session, metric_name)` | Full lineage path for a metric (all upstream tables) |
| `find_join_paths(db_session, table_a, table_b, max_depth=3)` | Used by NL2SQLAgent to discover join paths |
| `get_downstream_impact(db_session, table_name)` | Impact analysis — what metrics/dashboards are affected |
| `sync_semantic_layer_to_graph(db_session, cube_client)` | Nightly: syncs Cube cubes → AGE vertices |

---

## Alembic Migrations

**File:** `backend/app/db/migrations/env.py`

Standard Alembic configuration:
- Reads `sqlalchemy.url` from `settings.DATABASE_URL_SYNC`
- Uses `Base.metadata` for autogenerate support
- `poolclass=pool.NullPool` for migration safety

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "add new column"

# Apply migrations
uv run alembic upgrade head
```

---

## Database Rules (from CLAUDE.md)

- **Every table MUST have:** `id UUID PK DEFAULT gen_random_uuid()`, `created_at`, `updated_at`, `tenant_id FK`
- **RLS:** every user-data table enables row-level security
- **No dropping columns** — mark `deprecated_at TIMESTAMPTZ` first, remove after 2 sprints
- **Indexes:** all FKs and `tenant_id` columns indexed
- **Query timeout:** 30s via `SET LOCAL statement_timeout`
- **Migrations:** Alembic only — no manual `ALTER TABLE`
