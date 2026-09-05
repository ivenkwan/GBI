import { z } from "zod";

/** Chat request validation */
export const ChatRequestSchema = z.object({
  query: z.string().min(1, "Query cannot be empty").max(2000, "Query too long"),
  conversation_id: z.string().uuid().optional(),
  confirm_large_query: z.boolean().optional(),
});

export type ChatRequest = z.infer<typeof ChatRequestSchema>;

/** Chat response validation */
export const ChatResponseSchema = z.object({
  conversation_id: z.string(),
  session_id: z.string().optional(),
  query: z.string(),
  sql: z.string().optional(),
  sql_explanation: z.string().optional(),
  chart_spec: z.record(z.unknown()).optional(),
  narrative: z.string().optional(),
  chart_image_base64: z.string().optional(),
  chart_svg: z.string().optional(),
  warnings: z.array(z.string()),
});

export type ChatResponse = z.infer<typeof ChatResponseSchema>;

/** SSE event validation */
export const SSEEventSchema = z.object({
  event: z.enum([
    "start", "intent", "sql", "validation", "data",
    "chart", "narrative", "done",
  ]),
  conversation_id: z.string().optional(),
  intent: z.string().optional(),
  plan: z.array(z.record(z.unknown())).optional(),
  sql: z.string().nullable().optional(),
  valid: z.boolean().optional(),
  validated_sql: z.string().nullable().optional(),
  row_count: z.number().optional(),
  preview: z.array(z.record(z.unknown())).optional(),
  chart_spec: z.record(z.unknown()).optional(),
  image_base64: z.string().optional(),
  svg: z.string().optional(),
  narrative: z.string().nullable().optional(),
  status: z.string().optional(),
  error: z.string().optional(),
  warnings: z.array(z.string()).optional(),
  session_id: z.string().optional(),
  requires_confirmation: z.boolean().optional(),
  row_estimate: z.number().nullable().optional(),
});

export type SSEEvent = z.infer<typeof SSEEventSchema>;

/** Metric list response (GET /metrics/list) */
export const MetricSummarySchema = z.object({
  name: z.string(),
  title: z.string(),
  description: z.string(),
  metric_type: z.string(),
  cube_name: z.string(),
  measure_name: z.string(),
  dimensions: z.array(z.string()),
  time_dimensions: z.array(z.string()),
});

export type MetricSummary = z.infer<typeof MetricSummarySchema>;

export const MetricListResponseSchema = z.object({
  metrics: z.array(MetricSummarySchema),
  count: z.number(),
});

export type MetricListResponse = z.infer<typeof MetricListResponseSchema>;

/** Metric query (POST /metrics/query) */
export const MetricQueryRequestSchema = z.object({
  measures: z.array(z.string()).min(1).max(5),
  dimensions: z.array(z.string()).max(5).optional(),
  time_dimensions: z
    .array(
      z.object({
        dimension: z.string(),
        granularity: z.enum(["day", "week", "month", "quarter", "year", "hour"]),
      }),
    )
    .max(3)
    .optional(),
  filters: z
    .array(
      z.object({
        member: z.string(),
        operator: z.string(),
        values: z.array(z.string()).optional(),
      }),
    )
    .optional(),
  order: z.array(z.array(z.string())).optional(),
  limit: z.number().int().min(1).max(1000).optional(),
  offset: z.number().int().min(0).optional(),
  timezone: z.string().optional(),
});

export type MetricQueryRequest = z.infer<typeof MetricQueryRequestSchema>;

export const MetricQueryResponseSchema = z.object({
  data: z.array(z.record(z.unknown())),
  annotation: z.record(z.unknown()),
  total: z.number().nullable(),
  query: z.record(z.unknown()),
  latency_ms: z.number(),
  cached: z.boolean(),
});

export type MetricQueryResponse = z.infer<typeof MetricQueryResponseSchema>;

/** Chart AssemblyInput validation (Flint schema) */
export const ChartAssemblyInputSchema = z.object({
  chartType: z.string().min(1),
  encodings: z.record(
    z.object({
      field: z.string(),
      title: z.string().optional(),
    }),
  ),
  baseSize: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
  }),
  semantic_types: z
    .record(z.enum(["Category", "Quantity", "Temporal"]))
    .optional(),
  data: z.object({
    values: z.array(z.record(z.unknown())).optional(),
    url: z.string().url().optional(),
  }),
});

export type ChartAssemblyInput = z.infer<typeof ChartAssemblyInputSchema>;

/** Metric definition validation */
export const MetricDefinitionSchema = z.object({
  name: z.string(),
  title: z.string(),
  description: z.string(),
  metric_type: z.enum([
    "sum", "count", "count_distinct", "avg",
    "min", "max", "ratio", "derived", "running_total",
  ]),
  cube_name: z.string(),
  measure_name: z.string(),
  dimensions: z.array(z.string()),
  time_dimensions: z.array(z.string()),
  format: z.record(z.unknown()).nullable().optional(),
});

export type MetricDefinition = z.infer<typeof MetricDefinitionSchema>;

/** Login request validation */
export const LoginRequestSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

export type LoginRequest = z.infer<typeof LoginRequestSchema>;

/** Login response */
export const LoginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  user: z.object({
    id: z.string(),
    email: z.string(),
    name: z.string(),
    tenant_id: z.string(),
    roles: z.array(z.string()),
  }),
});

export type LoginResponse = z.infer<typeof LoginResponseSchema>;
