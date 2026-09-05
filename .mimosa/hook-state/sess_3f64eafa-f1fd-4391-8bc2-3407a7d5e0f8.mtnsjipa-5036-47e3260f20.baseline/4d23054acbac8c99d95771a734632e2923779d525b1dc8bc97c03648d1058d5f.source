# API Reference

> **Base URL:** `http://localhost:8000/api/v1` | **Auth:** JWT Bearer token | **Content-Type:** `application/json`

## Authentication

All endpoints except health checks require a JWT Bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

The token is obtained via `/auth/login` (not yet implemented in v1 API; see [Core Services](core-services.md#5-authentication) for JWT creation flow).

**Token payload:**
```json
{
  "sub": "<user_id>",
  "tenant_id": "<tenant_id>",
  "roles": ["user"],
  "exp": 1234567890,
  "iat": 1234567890
}
```

On failure (missing, expired, or invalid token): HTTP 401 with:
```json
{"code": "INVALID_TOKEN", "message": "Missing, expired, or invalid authentication token"}
```

**Implementation status key:** ✅ = fully implemented, ⚠️ = stub

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
⚠️ **Readiness probe.** Returns DB, Redis, and MCP status. Currently stubbed — actual DB/Redis pings marked as TODO.

**Response (stub):**
```json
{"status": "ready", "checks": {"database": "healthy", "redis": "healthy", "mcp": "healthy"}}
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
  "warnings": []
}
```

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
| `validation` | `validated_sql`, `warnings` | Validation agent cleared SQL |
| `data` | `row_count`, `warnings` | Query executed, data returned |
| `chart` | `chart_spec`, `image_base64`, `svg` | Chart generated + rendered |
| `narrative` | `narrative`, `warnings` | Narrative agent wrote insight |
| `done` | `status`, `warnings` | Pipeline complete |

**Example SSE stream:**
```
data: {"event":"start","conversation_id":"...","query":"Show revenue by region"}

data: {"event":"intent","intent":"chat_data","dispatch_plan":["nl2sql","validation","chart_gen","narrative"]}

data: {"event":"sql","sql":"SELECT region, SUM(revenue_amount) AS total FROM ...","warnings":[]}

data: {"event":"validation","is_valid":true,"validated_sql":"SET LOCAL statement_timeout = '30s'; SELECT ...","warnings":[]}

data: {"event":"done","status":"success","warnings":[]}
```

[see more...]

```

**Status values on `done`:** `success`, `no_sql`, `validation_failed`, `no_data`, `error`

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

## Datasources

> ⚠️ All endpoints are stubs.

### `GET /datasources`
List configured data sources for the current tenant.

### `POST /datasources/test`
Test a database connection.

---

## Metrics

> ⚠️ All endpoints are stubs. TODO: query Cube.dev meta API and dbt manifest.

### `GET /metrics/list`
List all metrics from the semantic layer.

### `POST /metrics/query`
Execute a metric query against Cube.dev.

---

## Reports

> ⚠️ All endpoints are stubs. TODO: implement report generation pipeline.

### `POST /reports/generate`
Generate a multi-chart report from a natural language prompt.

### `GET /reports/{report_id}`
Retrieve a previously generated report.

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
