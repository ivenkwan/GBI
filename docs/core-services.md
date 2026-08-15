# Core Services

> Backend infrastructure: configuration, logging, LLM client, caching, authentication, PII masking, observability.

---

## 1. Configuration

**File:** `backend/app/core/config.py` | **Type:** `pydantic-settings.BaseSettings`

Singleton: `settings = Settings()` — imported project-wide. Loads from `.env` with `extra="ignore"`.

| Category | Key | Default | Purpose |
|---|---|---|---|
| App | `APP_ENV` | `"development"` | `development` / `staging` / `production` |
| App | `DEBUG` | `True` | Debug mode toggle |
| App | `LOG_LEVEL` | `"DEBUG"` | loguru log level |
| App | `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| LLM | `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| LLM | `LLM_REASONING_MODEL` | `"claude-opus-4"` | Used for NL2SQL (thinking enabled) |
| LLM | `LLM_FAST_MODEL` | `"claude-haiku-4"` | Used for routing, charts, narrative |
| Database | `DATABASE_URL` | `postgresql+asyncpg://genbi:genbi@localhost:5432/genbi` | Async connection |
| Database | `DATABASE_URL_SYNC` | `postgresql+psycopg2://genbi:genbi@localhost:5432/genbi` | Sync (Alembic) |
| Redis | `REDIS_URL` | `redis://localhost:6379/0` | Cache + session store |
| Semantic | `CUBE_API_URL` | `http://localhost:4000/cubejs-api/v1` | Cube.dev REST endpoint |
| Semantic | `CUBE_API_SECRET` | `""` | Cube API auth |
| Obs. | `LANGFUSE_SECRET_KEY` | `""` | Langfuse LLM tracing |
| Obs. | `LANGFUSE_PUBLIC_KEY` | `""` | Langfuse public key |
| Obs. | `LANGFUSE_HOST` | `"https://cloud.langfuse.com"` | Langfuse instance |
| Auth | `JWT_SECRET_KEY` | `"change-me"` | HS256 signing key |
| Auth | `JWT_ALGORITHM` | `"HS256"` | JWT algorithm |
| Auth | `JWT_EXPIRE_MINUTES` | `60` | Token lifetime |
| Tenant | `TENANT_ENCRYPTION_KEY` | `""` | PII encryption key |
| Flint | `FLINT_MCP_BACKENDS` | `"vegalite,echarts,chartjs"` | Enabled chart backends |
| Flint | `FLINT_MCP_DATA_ROOTS` | `"/tmp/genbi-charts"` | Temp data directory |

---

## 2. Logging

**File:** `backend/app/core/logging.py`

Uses **loguru** (not stdlib logging). A single shared `logger` instance.

```python
from app.core.logging import logger
logger.info("LLM call complete", model="claude-opus-4", latency_ms=1200)
```

**`setup_logging()`** — called once at app startup:
- **Development:** colored stdout at `settings.LOG_LEVEL`
- **Production:** adds daily-rotated JSON file output to `logs/genbi_*.json`, 30-day retention

---

## 3. LLM Client

**File:** `backend/app/core/llm_client.py`

### `LLMClient` (singleton)

All agent LLM calls route through `get_llm_client()`.

**Primary method:**
```python
async def invoke(
    self,
    messages: list[dict],
    system: str,
    use_reasoning: bool = False,
    options: LLMCallOptions | None = None,
    user_id: str = "",
    tenant_id: str = "",
    session_id: str = "",
    generated_sql: str = "",
) -> LLMCallResult
```

**Behavior:**
- `use_reasoning=True` → selects `LLM_REASONING_MODEL` (Opus-4), forces `thinking=True` and `temp=0.0`
- `use_reasoning=False` → selects `LLM_FAST_MODEL` (Haiku-4)
- **Retry:** up to 3 attempts, exponential backoff with jitter (`min(2^attempt + random, 30)` seconds)
- **JSON extraction:** three strategies — pure JSON, `` ```json `` code block, first `{...}` pair
- **Token budget:** warns via logger if `input+output > token_budget` (default 100K)
- **Audit logging:** calls audit callback after each successful invocation (SHA-256 of the prompt text — never raw — user/tenant/session context, token counts, latency, generated SQL). Since Phase 12 the callback is wired at app startup to `app/services/audit.py::write_audit_entry`, which persists one `audit_log` row per LLM call (asyncpg on `genbi_app`, tenant GUC set per row, fail-open).

### `LLMCallOptions`
```python
@dataclass
class LLMCallOptions:
    temperature: float = 0.0
    max_tokens: int = 4096
    thinking: bool = False
    response_format: str | None = None   # "json" triggers structured output extraction
    timeout_seconds: int = 60
    max_retries: int = 3
    token_budget: int = 100_000
```

### `load_prompt(name: str) -> str`
Reads from `.claude/prompts/{name}.md` relative to project root.

**Dependencies:** `langchain_anthropic.ChatAnthropic`, `settings.ANTHROPIC_API_KEY`.

---

## 4. Cache Service

**File:** `backend/app/core/cache.py` | **Architecture:** Dual-tier (L1 in-memory LRU + L2 shared Redis)

### Cache TTLs (`CacheTTL`)

| Constant | Value | Purpose |
|---|---|---|
| `SCHEMA_EMBEDDINGS` | 24h | Nightly-synced from information_schema |
| `METRIC_DEFINITIONS` | 5 min | Cube.dev `/meta` response |
| `QUERY_RESULTS` | 5 min | Read-heavy analytics |
| `LLM_RESPONSE` | 1h | Same query = same SQL at temp=0 |
| `CHART_SPEC` | 1h | Vega-Lite/ECharts specs |
| `RATE_LIMIT` | 1 min | Window counters |
| `SESSION_STATE` | 30 min | Idle session expiry |

### `LRUCache` (Level 1)

In-memory `OrderedDict`-based. Max 1000 entries. TTL-based expiry on `get()`. LRU eviction on `set()` when over capacity.

### `RedisCache` (Level 2)

Lazy-init via `redis.asyncio.from_url(settings.REDIS_URL)`. If Redis is unavailable, all operations become no-ops (graceful degradation).

### `CacheService` (Unified facade)

**Typed get/set pairs (all async):**

| Method pair | Key pattern | Tier |
|---|---|---|
| `get_schema_context` / `set_schema_context` | `genbi:{tenant}:schema:{query_hash}` | L1+L2 |
| `get_metric_definitions` / `set_metric_definitions` | `genbi:{tenant}:metrics:all` | L1+L2 |
| `get_query_result` / `set_query_result` | `genbi:{tenant}:query:{sql_hash}` | L1+L2 |
| `get_llm_response` / `set_llm_response` | `genbi:{tenant}:llm:{prompt_hash}` | L2 only |
| `get_chart_spec` / `set_chart_spec` | `genbi:{tenant}:chart:{data_hash}` | L1+L2 |
| `get_session` / `set_session` | `genbi:session:{session_id}` | L2 only |
| `check_rate_limit` | `genbi:ratelimit:{user}` | L2 only |

**Read path:** L1.get() → hit? return. Miss → L2.get() → hit? promote to L1 → return. Miss → return None.

**Rate limiting:** `check_rate_limit(user_id, max_requests=30, window_seconds=60) → (allowed: bool, remaining: int)`. Uses Redis INCR + EXPIRE. Falls open (allows all) if Redis is down.

---

## 5. Authentication

**File:** `backend/app/core/auth.py`

### JWT Creation and Verification

```python
from app.core.auth import create_access_token, decode_token

token = create_access_token(
    user_id="550e8400-e29b-41d4-a716-446655440000",
    tenant_id="00000000-0000-0000-0000-000000000001",
    roles=["user", "analyst"],
    expires_minutes=60
)

payload = decode_token(token)
# payload = {"sub": "...", "tenant_id": "...", "roles": [...], "exp": ..., "iat": ...}
```

### `get_current_user` Dependency

FastAPI `Depends(get_current_user)` extracts the Bearer token from `HTTPBearer`, decodes it with `python-jose`, and returns the payload dict. On failure: HTTP 401.

**Used by:** All API routes except health checks (see [API Reference](api-reference.md)).

---

## 6. PII Masking

**File:** `backend/app/core/masking.py`

### `PIIMasker`

Column-level masking for PII fields. Per-tenant, role-aware.

```python
masker = PIIMasker()  # uses DEFAULT_MASK_RULES
masked_rows = masker.mask_rows(rows)
```

**Pre-configured rules** for 14 column name patterns: `email`, `phone`, `ssn`, `credit_card`, `password`, `secret`, `api_key`, `token`, etc.

**Mask strategies:**
| MaskType | Input | Output |
|---|---|---|
| `EMAIL` | `jdoe@company.com` | `j***@company.com` |
| `PHONE` | `+1-555-123-4567` | `***-***-4567` |
| `SSN` | `123-45-6789` | `***-**-6789` |
| `CREDIT_CARD` | `4111-1111-1111-1111` | `****-****-****-1111` |
| `FULL_MASK` | anything | `****` |

**Tenant-aware routing:**
```python
load_tenant_mask_rules(tenant_id, custom_rules)
masker = get_masker_for_tenant(tenant_id)
```

---

## 7. Observability

**File:** `backend/app/core/observability.py`

### Tracing (OpenTelemetry)
- `init_tracing()` — creates OTLP gRPC exporter + console exporter (debug), registers `genbi-backend` service
- `instrument_app(app)` — auto-instruments FastAPI, HTTPX, and SQLAlchemy
- `create_span(name, attributes)` — context manager for manual spans
- `get_current_trace_id()` — returns 32-hex OTel trace ID

### Metrics (Prometheus)
`init_metrics()` registers these gauges/counters/histograms on the `genbi` meter:

| Metric | Type | Description |
|---|---|---|
| `genbi.chat.requests` | Counter | Chat endpoint invocations |
| `genbi.chat.latency` | Histogram | End-to-end chat latency (ms) |
| `genbi.sql.generated` | Counter | SQL queries produced |
| `genbi.sql.validation_failures` | Counter | Failed validation checks |
| `genbi.llm.tokens` | Counter | LLM token consumption |
| `genbi.llm.latency` | Histogram | Per-LLM-call latency (ms) |
| `genbi.cache.hits` | Counter | Cache hit count |
| `genbi.cache.misses` | Counter | Cache miss count |

### Langfuse (LLM Tracing)
`LangfuseTracer.trace_llm_call()` creates a Langfuse trace with a sub-generation span. Truncates I/O to 2000 chars. Gracefully degrades if unavailable.

---

## Cross-Cutting Patterns

**Graceful degradation:** Redis unavailable → no-op caching. Langfuse unavailable → skip tracing. OTel endpoint missing → skip export. Audit callback failure → log and continue.

**Singletons:** `get_cache()`, `get_llm_client()`, `get_langfuse_tracer()` use module-level lazy-init (no locking — safe under asyncio).

**Tenant isolation:** All cache keys embed `{tenant_id}`. JWT tokens carry `tenant_id`. Masking rules are per-tenant. Audit logs link to `tenants` via FK.

**Async everywhere:** All I/O-bound services use `async`/`await`.
