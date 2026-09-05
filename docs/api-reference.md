# API Reference

> **Base URL:** `http://localhost:8000/api/v1` | **Auth:** JWT Bearer token | **Content-Type:** `application/json`

## Authentication

All endpoints except health checks require a JWT Bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

The token is obtained via `POST /auth/login` (below).

**Token payload:**
```json
{
  "sub": "<user_id>",
  "tenant_id": "<tenant_id>",
  "roles": ["user"],
  "platform_admin": false,
  "exp": 1234567890,
  "iat": 1234567890
}
```

`platform_admin: true` (planned, ADR 009 / Phase 21) marks an active
platform-superuser grant; the `require_platform_admin` guard re-verifies the
grant table behind a 60-second cache, so revocation takes effect within a
minute rather than at token expiry.

On failure (missing, expired, or invalid token): HTTP 401 with:
```json
{"code": "INVALID_TOKEN", "message": "Missing, expired, or invalid authentication token"}
```

**Implementation status key:** ✅ = fully implemented, ⚠️ = stub

---

## Auth

### `POST /auth/login`
✅ **Authenticate a user by email + password and receive a JWT access token.**

**Request:** `LoginRequest`
```json
{
  "email": "admin@genbi.local",
  "password": "admin123"
}
```

| Field | Type | Constraints |
|---|---|---|
| `email` | `string` | Required, 3–255 chars (normalized to lowercase) |
| `password` | `string` | Required, 6–128 chars |
| `tenant_id` | `string \| null` | Optional UUID — required only when the same email exists in multiple tenants |

**Response:** `LoginResponse`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "00000000-0000-0000-0000-000000000101",
    "email": "admin@genbi.local",
    "name": "admin",
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "roles": ["admin", "user"]
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `access_token` | `string` | JWT, signed with `JWT_SECRET_KEY`; accepted by every protected endpoint |
| `user.name` | `string` | Derived from the email local-part (the `users` table has no name column) |

**Errors:** `401` with `{"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}` for wrong credentials, unknown email, ambiguous multi-tenant email, or an invalid `tenant_id`. `429` with `{"code": "TOO_MANY_ATTEMPTS", ...}` after 5 failed attempts for the same email within 15 minutes (counter resets on success).

---

## Health

> No auth required.

### `GET /health`
✅ **Liveness probe.** Returns 200 if the server is running.

**Response:**
```json
{"status": "ok", "version": "0.1.0"}
```

### `GET /health/ready`
✅ **Readiness probe.** Pings Postgres and Redis for real; returns 200 only when both are reachable, 503 otherwise (the probe used by Docker healthchecks and `make verify`).

**Response:**
```json
{"status": "ready", "database": "connected", "redis": "connected", "mcp_flint": "configured"}
```

---

## Chat

> `Authorization: Bearer <token>` required.

### `POST /chat`
✅ Main NL-to-SQL endpoint. Returns SQL, chart spec, and narrative in a single response.

**Request:** `ChatRequest`
```json
{
  "query": "Show total revenue by region for Q3",
  "conversation_id": null
}
```

| Field | Type | Constraints |
|---|---|---|
| `query` | `string` | Required, 1–5000 chars |
| `conversation_id` | `string \| null` | Optional UUID for multi-turn |
| `confirm_large_query` | `bool` | Default false — set true to proceed when the EXPLAIN row estimate exceeds 1M (see below) |

**Response:** `ChatResponse`
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "Show total revenue by region for Q3",
  "sql": "SELECT region, SUM(revenue_amount) as total_revenue FROM transactions WHERE ...",
  "sql_explanation": "This query groups revenue by region using the transactions table...",
  "chart_spec": {"chartType": "Bar Chart", "encodings": {...}},
  "narrative": "Revenue in Q3 was highest in the Northeast region at $4.2M...",
  "chart_image_base64": null,
  "warnings": [],
  "requires_confirmation": false,
  "row_estimate": 1200
}
```

**Large-query confirmation:** when the validated SQL's EXPLAIN estimate exceeds 1M rows, the response returns early with `requires_confirmation: true`, `row_estimate`, the SQL, and warnings — no data, chart, or narrative. Re-send the same query with `confirm_large_query: true` to execute.

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | `string` | UUID generated per session |
| `query` | `string` | Echoes the input query |
| `sql` | `string \| null` | Generated read-only SQL |
| `sql_explanation` | `string \| null` | Plain-English explanation |
| `chart_spec` | `dict \| null` | Flint `ChartAssemblyInput` schema |
| `narrative` | `string \| null` | 3–5 sentence insight paragraph |
| `chart_image_base64` | `string \| null` | Rendered chart (PNG) |
| `warnings` | `string[]` | Advisory messages |

### `POST /chat/feedback`
✅ Record thumbs-up/down feedback on a chat response (Phase 15).

**Request:** `{"session_id": "<uuid>", "score": 1}` — score: `1` up, `-1` down, `0` clear. The `session_id` is the one from the SSE `start` event / sync response (NOT the conversation id).

The score lands on the audit rows of the session (`audit_log.feedback_score`), completing the governance loop.

Errors: `503` `FEEDBACK_UNAVAILABLE` (no matching audit rows or store unreachable), `422` validation.

### `POST /chat/stream`
✅ **Streaming variant.** Returns SSE events as the agent pipeline progresses.

**Request:** Same as `POST /chat`.

**Response:** `text/event-stream` — each event is `data: {json}\n\n`.

**SSE Event Types:**

| Event | Fields | Description |
|---|---|---|
| `start` | `conversation_id`, `query` | Pipeline started |
| `intent` | `intent`, `dispatch_plan` | Router classified the query |
| `sql` | `sql`, `warnings` | NL2SQL agent generated SQL |
| `validation` | `valid`, `validated_sql`, `requires_confirmation`, `row_estimate`, `warnings` | Validation gate (EXPLAIN-backed) |
| `data` | `row_count`, `warnings` | Query executed, data returned |
| `chart` | `chart_spec`, `image_base64`, `svg` | Chart generated + rendered |
| `narrative` | `narrative`, `warnings` | Narrative agent wrote insight |
| `done` | `status`, `warnings` | Pipeline complete |

**Example SSE stream:**
```
data: {"event":"start","conversation_id":"...","query":"Show revenue by region"}

data: {"event":"intent","intent":"chat_data","dispatch_plan":["nl2sql","validation","chart_gen","narrative"]}

data: {"event":"sql","sql":"SELECT region, SUM(revenue_amount) AS total FROM ...","warnings":[]}

data: {"event":"validation","valid":true,"validated_sql":"SELECT region, SUM(revenue_amount) AS total FROM ...","requires_confirmation":false,"row_estimate":1200,"warnings":[]}

data: {"event":"done","status":"complete","warnings":[]}
```

[see more...]

```

**Status values on `done`:** `complete`, `no_sql`, `validation_failed`, `confirmation_required` (>1M-row estimate — re-send with `confirm_large_query: true`), `no_data`, `error`

---

## Charts

> `Authorization: Bearer <token>` required.

### `POST /charts/render`
✅ Render a chart from a `ChartAssemblyInput` spec. Supports Vega-Lite, ECharts, and Chart.js backends.

**Request:** `ChartRenderRequest`
```json
{
  "spec": {
    "chartType": "Bar Chart",
    "encodings": {
      "x": {"field": "region"},
      "y": {"field": "revenue_total"}
    },
    "baseSize": {"width": 600, "height": 400},
    "semantic_types": {"region": "Category", "revenue_total": "Quantity"},
    "data": {
      "values": [
        {"region": "Northeast", "revenue_total": 4200000},
        {"region": "West", "revenue_total": 3100000}
      ]
    }
  },
  "backend": "vegalite",
  "format": "png"
}
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `spec.chartType` | `string` | — | Bar, Line, Scatter, Pie, Area, etc. (31 supported) |
| `spec.encodings` | `dict` | — | Field → channel mappings (`x`, `y`, `color`, `size`, etc.) |
| `spec.baseSize` | `{width, height}` | `{600, 400}` | Output dimensions |
| `spec.semantic_types` | `dict` | — | Field types: `Category`, `Quantity`, `Temporal` |
| `spec.data.values` | `object[]` | — | Inline data rows (≤ 100 rows; larger → temp file) |
| `spec.data.url` | `string` | — | Alternative: file URL for large datasets |
| `backend` | `string` | `"vegalite"` | `"vegalite"`, `"echarts"`, or `"chartjs"` |
| `format` | `string` | `"png"` | `"png"` or `"svg"` |

**Response:** `ChartRenderResponse`
```json
{
  "success": true,
  "format": "png",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgA...",
  "svg": null,
  "warnings": [],
  "errors": []
}
```

---

## Conversations

> Multi-turn chat history (Phase 14). Requires `Authorization: Bearer <token>`.

### `GET /conversations`
✅ List the current user's conversations, most recently active first (RLS tenant-scoped + per-user).

**Response:** `{conversations: [{id, title, created_at, updated_at}], count}`

Errors: `503` `PERSISTENCE_UNAVAILABLE` when the store is unreachable.

### `GET /conversations/{conversation_id}/messages`
✅ A conversation's turns in chronological order (most recent 50 by default). Other tenants' ids return zero messages (RLS).

**Response:** `{messages: [{role, content, generated_sql?, created_at}], count}`

Errors: `400 INVALID_CONVERSATION` (malformed id), `503 PERSISTENCE_UNAVAILABLE`.

**Multi-turn flow:** send chat requests with the same `conversation_id`; the NL2SQL agent receives the prior turns as a "Conversation History" prompt section (follow-ups like "now break that down by region" work). The SSE `start` event carries the resolved `conversation_id`; turns persist automatically (fail-open).

---

## Datasources

### `GET /datasources`
✅ List the semantic layer's cubes for the current tenant (from Cube `/meta`).

**Response:**
```json
{
  "datasources": [
    {"name": "Sales", "title": "Sales", "measures": 4, "dimensions": 4}
  ],
  "count": 1
}
```

Errors: `503` `{"detail": {"code": "CUBE_UNAVAILABLE", ...}}` when Cube is unreachable.

### `POST /datasources/test`
⚠️ Stub. Targets a different feature (admin-configured external warehouses), not the built-in semantic-layer source.

---

## Metrics

### `GET /metrics/list`
✅ List all metrics from the semantic layer (catalog of 10 cubes / 23 measures).

**Response:** `{metrics: [{name, title, description, metric_type, cube_name, measure_name, dimensions, time_dimensions}], count}`

### `POST /metrics/query`
✅ Execute a **tenant-scoped** metric query against Cube.dev (ADR 008: the JWT's tenant claim drives Cube's per-tenant driver and its RLS GUC — results are isolated at the database layer).

**Request:**
```json
{
  "measures": ["Sales.revenue_total"],
  "dimensions": ["Sales.region"],
  "time_dimensions": [{"dimension": "Sales.transaction_date", "granularity": "month"}],
  "limit": 100
}
```

| Field | Type | Constraints |
|---|---|---|
| `measures` | `string[]` | 1–5, must exist in the catalog (`400 INVALID_METRIC` otherwise) |
| `dimensions` | `string[]?` | ≤ 5 group-bys |
| `time_dimensions` | `[{dimension, granularity, date_range?}]?` | ≤ 3; granularity: day/week/month/quarter/year/hour |
| `filters` | `[{member, operator, values?}]?` | Cube filter syntax |
| `order` | `[[field, dir]]?` | e.g. `[["Sales.revenue_total", "desc"]]` |
| `limit` / `offset` | `int` | 1–1000 / ≥ 0 |
| `timezone` | `string` | default `UTC` |

**Response:** `{data: [...flattened rows...], annotation, total, query, latency_ms, cached}` — row keys are stripped of cube prefixes. Results are cached per tenant for 300s (same query → `cached: true`).

Errors: `400 INVALID_METRIC`, `503 CUBE_UNAVAILABLE`, `422` validation.

---

## Reports

> Multi-chart reports (Phase 16). Requires `Authorization: Bearer <token>`.

### `POST /reports/generate`
✅ Generate a multi-chart report from a natural language prompt.

LLM-planned (one fast-model call picks 2–4 metrics from the semantic-layer catalog) with deterministic execution: per-section tenant-scoped Cube query → chart render → one overall narrative. Sections that return no data are skipped with a warning; the report persists best-effort.

**Request:**
```json
{"prompt": "Q3 performance: revenue, pipeline, and active users", "max_sections": 3}
```

| Field | Type | Constraints |
|---|---|---|
| `prompt` | `string` | Required, 1–2000 chars |
| `max_sections` | `int` | 2–4, default 3 |

**Response:** `ReportOut` — `{report_id, title, prompt, summary?, status, created_at, sections: [{position, metric_name, section_title, chart_spec, chart_svg?, data_total?, row_count, narrative?}], warnings}`

Errors: `503` `REPORT_GENERATION_FAILED` (planning/exec failure), `422` validation.

### `GET /reports`
✅ List the current user's reports, newest first.

**Response:** `{reports: [{id, title, created_at, section_count}], count}`

Errors: `503` `PERSISTENCE_UNAVAILABLE`.

### `GET /reports/{report_id}`
✅ Retrieve a persisted report (RLS tenant-scoped).

**Response:** same `ReportOut` shape as generate.

Errors: `400` `INVALID_REPORT` (malformed id), `404` `REPORT_NOT_FOUND`, `503` `PERSISTENCE_UNAVAILABLE`.

---

## Error Format

All error responses follow this shape:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of what went wrong"
  }
}
```

**Common error codes:**

| Code | HTTP Status | Context |
|---|---|---|
| `INVALID_TOKEN` | 401 | Missing, expired, or invalid JWT |
| `VALIDATION_FAILED` | 422 | Request body fails Pydantic validation |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Pydantic Models (reference)

### `ChatRequest`
```python
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str | None = Field(None)
```

### `ChartAssemblyInput`
```python
class ChartAssemblyInput(BaseModel):
    chartType: str
    encodings: dict  # Record[str, FieldSpec]
    baseSize: dict   # {"width": int, "height": int}
    semantic_types: dict[str, str] | None
    data: dict        # {"values": list[dict]} or {"url": str}
```

### `ChartRenderRequest`
```python
class ChartRenderRequest(BaseModel):
    spec: ChartAssemblyInput
    backend: str = Field(default="vegalite")
    format: str = Field(default="png")
```

---

# Planned API — Multi-Tenancy Control Plane & Knowledge Base

> **Implementation status:** Admin (Phase 21) ✅ built. Tenant Users
> (Phase 23), Wiki (Phase 24), and BYOK (Phases 25–26) remain planned —
> their contracts below are the agreed design targets.

## Admin (platform superuser) — ADR 009 ✅ (Phase 21)

Guard: `require_platform_admin` (JWT `platform_admin` claim + 60s-cached
grant-table re-check → 403 NOT_PLATFORM_ADMIN; fails open on outage).
Every mutation writes an `admin_audit` row. Suspension is enforced at
request time the same way (403 TENANT_SUSPENDED).

| Method + Path | Purpose |
|---|---|
| `GET /admin/stats` | Platform counters: tenants by status, users, LLM calls (24h), active schedules |
| `GET /admin/tenants` | Tenant list with per-tenant counters (users, reports, dashboards, wiki pages) |
| `POST /admin/tenants` | Provision: `{name, slug, admin_email, temp_password?, seed_sample_data?}` → tenant + initial tenant-admin user (transactional) |
| `GET /admin/tenants/{id}` | Detail: users, schedules, counters, recent admin audit for the tenant |
| `PATCH /admin/tenants/{id}` | Rename / set `status: active\|suspended` / merge `settings` JSONB |
| `DELETE /admin/tenants/{id}?confirm=yes` | Decommission — guarded; refuses while users exist unless `force=true` (cascades tenant data; audit rows retained) |
| `GET /admin/admins` | Active platform superusers + full grant/revoke history |
| `POST /admin/admins` | Grant superuser `{user_id \| email}` |
| `DELETE /admin/admins/{user_id}` | Revoke (effective ≤ 60s via cached re-check) |
| `GET /admin/audit` | Admin-action feed; filters: `actor_id`, `target_type`, `tenant_id`, time window |

Errors: `403 NOT_PLATFORM_ADMIN`, `400 INVALID_SLUG`, `409 TENANT_EXISTS`,
`409 USER_EXISTS`, `422 TENANT_NOT_EMPTY` (delete without force),
`403 TENANT_SUSPENDED` (on any authenticated endpoint for suspended tenants).

## Tenant Users — ADR 009 §6 / Phase 23 ✅ (built)

Guard: tenant `admin` role or platform superuser (user management is
in-tenant; platform admins act cross-tenant through the same endpoints).

| Method + Path | Purpose |
|---|---|
| `GET /users` | List the tenant's users (id, email, roles, created_at, last_login_at) |
| `POST /users` | Create user `{email, password, roles}` (roles ⊆ `user`, `admin`) |
| `PATCH /users/{id}` | Update email / roles / enable-disable (`status`) |
| `POST /users/{id}/reset-password` | Admin sets a new password (invalidates nothing — JWTs are short-lived) |
| `DELETE /users/{id}` | Hard delete; refused for the last active admin of a tenant |
| `GET /auth/me` | Current identity: id, email, tenant, roles, platform_admin |
| `POST /auth/change-password` | Self-service password change (current password required) |

Deletes keep audit history (`audit_log.user_id` has no FK by design);
conversations/reports/dashboards owned by the user remain (tenant-owned
assets) — documented in ADR 009.

## Wiki (tenant knowledge base) — ADR 010

Read: any tenant user. Write: tenant `admin` or platform superuser.
All reads/writes RLS-scoped via the tenant GUC.

| Method + Path | Purpose |
|---|---|
| `GET /wiki` | Page list as a tree (`parent_slug` hierarchy) |
| `GET /wiki/{slug}` | Current page (markdown) |
| `PUT /wiki/{slug}` | Create-or-update — appends a revision atomically |
| `DELETE /wiki/{slug}` | Delete page + its revisions |
| `GET /wiki/{slug}/history` | Revision list (version, editor, timestamp) |
| `POST /wiki/{slug}/restore/{version}` | Restore forward as a new revision |
| `GET /wiki/search?q=` | pgvector top-k over `wiki_embeddings` (ILIKE fallback on fail-open) |

Agent integration (same phase): retrieved wiki chunks feed a
`## Tenant Knowledge` section of the NL2SQL prompt, and the router's
`chat_knowledge` intent answers from wiki search directly.

## BYOK LLM Providers (tenant + admin) — ADR 011 (planned, Phases 25–26)

> Planned (Phases 25–26 — not yet built). Writes validate the candidate
> config with a live 1-token provider ping; reads are always masked — the
> API key is write-only and never returned (only `key_last4`).

| Method + Path | Guard | Purpose |
|---|---|---|
| `GET /settings/llm` | tenant user | Own config, masked: provider, base_url, models, key_last4, key_version, status, updated_at |
| `PUT /settings/llm` | tenant `admin` \| superuser | Create/replace `{provider, api_key, base_url?, reasoning_model, fast_model, embedding_model?}` — validates, bumps key_version, audits |
| `POST /settings/llm/validate` | tenant `admin` \| superuser | Test a candidate config without saving |
| `DELETE /settings/llm` | tenant `admin` \| superuser | Remove the config — LLM calls revert to the platform key |
| `GET /admin/tenants/{id}/llm` | platform superuser | Masked tenant config + usage-by-model/provider (from audit_log) |
| `PUT /admin/tenants/{id}/llm` | platform superuser | Force-set on behalf of a tenant (same validation + audit) |

Errors: `400 BYOK_VALIDATION_FAILED` (sanitized provider message),
`503 BYOK_NOT_CONFIGURED` (platform `TENANT_ENCRYPTION_KEY` missing),
`LLM_BYOK_MISCONFIGURED` warning on chat degradation when a configured
tenant key fails auth — by design there is **no silent fallback** to the
platform key for configured tenants (ADR 011 §5).
