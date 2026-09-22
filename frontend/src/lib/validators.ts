import { z } from "zod";

/** Chat request validation */
export const ChatRequestSchema = z.object({
  query: z.string().min(1, "Query cannot be empty").max(2000, "Query too long"),
  conversation_id: z.string().uuid().optional(),
  confirm_large_query: z.boolean().optional(),
});

export type ChatRequest = z.infer<typeof ChatRequestSchema>;

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

export const MetricListResponseSchema = z.object({
  metrics: z.array(
    z.object({
      name: z.string(),
      title: z.string(),
      description: z.string(),
      metric_type: z.string(),
      cube_name: z.string(),
      measure_name: z.string(),
      dimensions: z.array(z.string()),
      time_dimensions: z.array(z.string()),
    }),
  ),
  count: z.number(),
});

export type MetricListResponse = z.infer<typeof MetricListResponseSchema>;

export const MetricQueryResponseSchema = z.object({
  data: z.array(z.record(z.unknown())),
  annotation: z.record(z.unknown()),
  total: z.number().nullable(),
  query: z.record(z.unknown()),
  latency_ms: z.number(),
  cached: z.boolean(),
});

export type MetricQueryResponse = z.infer<typeof MetricQueryResponseSchema>;

/** Login request validation */
export const LoginRequestSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

export type LoginRequest = z.infer<typeof LoginRequestSchema>;

/** Admin tenant provisioning (Phase 22) */
export const TenantProvisionSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  slug: z
    .string()
    .regex(/^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/, "Slug: 3–50 lowercase letters, digits, hyphens"),
  admin_email: z.string().email("Invalid admin email"),
  seed_sample_data: z.boolean(),
});

export type TenantProvision = z.infer<typeof TenantProvisionSchema>;

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

/** BYOK LLM provider config (Phase 26, ADR 011) */
export const LLMConfigSchema = z.object({
  provider: z.enum(["anthropic", "openai"]),
  api_key: z.string().min(8, "API key looks too short").max(512),
  base_url: z
    .string()
    .url("Base URL must be a valid URL (OpenAI-compatible gateways)")
    .max(512)
    .optional()
    .or(z.literal("")),
  reasoning_model: z.string().min(1, "Reasoning model is required").max(100),
  fast_model: z.string().min(1, "Fast model is required").max(100),
  embedding_model: z.string().max(100).optional().or(z.literal("")),
});

export type LLMConfigForm = z.infer<typeof LLMConfigSchema>;
