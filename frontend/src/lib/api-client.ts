/** API client — centralized HTTP layer for all backend calls.
 *
 * Every frontend data-fetch goes through this module.
 * Never call fetch() directly in components.
 */

import type { ChartAssemblyInput } from "@/types/chart";
import { getStoredToken } from "@/lib/auth-storage";

// Normalized to a trailing slash so relative paths resolve against the base
// path (e.g. "chat" against "http://host:8000/api/v1/" keeps /api/v1).
const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(
  /\/?$/,
  "/",
);

// Every request URL must resolve to exactly this origin, http(s) only — a
// path can never redirect the client to another host, scheme, or port.
const API_ORIGIN = new URL(API_BASE).origin;

function apiUrl(path: string): string {
  const url = new URL(path.replace(/^\//, ""), API_BASE);
  if (url.origin !== API_ORIGIN || !url.protocol.startsWith("http")) {
    throw new Error(`Refusing URL outside the configured API origin: ${url.origin}`);
  }
  return url.toString();
}

// Fixed relative route resolved against the configured base at module load —
// no runtime string can influence scheme, host, or port here.
const CHAT_STREAM_URL = new URL("/chat/stream", API_BASE).toString();

interface RequestOptions {
  method?: string;
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(apiUrl(path), {
    method: options.method ?? "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(res.status, error.code ?? "UNKNOWN", error.message ?? "Request failed");
  }

  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// --- Chat ---

export interface ChatRequest {
  query: string;
  conversation_id?: string;
  confirm_large_query?: boolean;
}

export interface ChatResponse {
  conversation_id: string;
  session_id?: string;
  query: string;
  sql?: string;
  sql_explanation?: string;
  chart_spec?: Record<string, unknown>;
  narrative?: string;
  chart_image_base64?: string;
  chart_svg?: string;
  warnings: string[];
  requires_confirmation?: boolean;
  row_estimate?: number | null;
}

export function sendChat(req: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", { method: "POST", body: req });
}

/** Thumbs feedback on a completed response (score: 1 up, -1 down, 0 clear). */
export function sendFeedback(
  sessionId: string,
  score: 1 | -1 | 0,
): Promise<{ status: string; session_id: string; score: number }> {
  return request("/chat/feedback", { method: "POST", body: { session_id: sessionId, score } });
}

export function streamChat(
  req: ChatRequest,
  onEvent: (event: Record<string, unknown>) => void,
  onError: (error: Error) => void,
): AbortController {
  const controller = new AbortController();
  const token = getStoredToken();

  fetch(CHAT_STREAM_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(req),
    signal: controller.signal,
  })
    .then(async (res) => {
      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              onEvent(event);
            } catch {
              // Skip unparseable chunks
            }
          }
        }
      }
    })
    .catch(onError);

  return controller;
}

// --- Charts ---

export interface ChartRenderRequest {
  spec: ChartAssemblyInput;
  backend?: string;
  format?: string;
}

export interface ChartRenderResponse {
  success: boolean;
  format: string;
  image_base64?: string;
  svg?: string;
  warnings: string[];
  errors: string[];
}

export function renderChart(req: ChartRenderRequest): Promise<ChartRenderResponse> {
  return request<ChartRenderResponse>("/charts/render", { method: "POST", body: req });
}

// --- Metrics ---

export interface MetricSummary {
  name: string;
  title: string;
  description: string;
  metric_type: string;
  cube_name: string;
  measure_name: string;
  dimensions: string[];
  time_dimensions: string[];
}

export interface MetricListResponse {
  metrics: MetricSummary[];
  count: number;
}

export function listMetrics(): Promise<MetricListResponse> {
  return request<MetricListResponse>("/metrics/list");
}

export interface MetricQueryRequest {
  measures: string[];
  dimensions?: string[];
  time_dimensions?: { dimension: string; granularity: string }[];
  filters?: { member: string; operator: string; values?: string[] }[];
  order?: string[][];
  limit?: number;
  offset?: number;
  timezone?: string;
}

export interface MetricQueryResponse {
  data: Record<string, unknown>[];
  annotation: Record<string, unknown>;
  total: number | null;
  query: Record<string, unknown>;
  latency_ms: number;
  cached: boolean;
}

export function queryMetrics(req: MetricQueryRequest): Promise<MetricQueryResponse> {
  return request<MetricQueryResponse>("/metrics/query", { method: "POST", body: req });
}

export interface DatasourceSummary {
  name: string;
  title: string;
  measures: number;
  dimensions: number;
}

export function listDatasources(): Promise<{ datasources: DatasourceSummary[]; count: number }> {
  return request<{ datasources: DatasourceSummary[]; count: number }>("/datasources");
}

// --- Conversations ---

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  generated_sql?: string | null;
  created_at: string;
}

export function listConversations(): Promise<{
  conversations: ConversationSummary[];
  count: number;
}> {
  return request<{ conversations: ConversationSummary[]; count: number }>("/conversations");
}

export function listConversationMessages(
  conversationId: string,
): Promise<{ messages: ConversationMessage[]; count: number }> {
  return request<{ messages: ConversationMessage[]; count: number }>(
    `/conversations/${conversationId}/messages`,
  );
}

// --- Reports ---

export interface ReportSection {
  position: number;
  metric_name: string;
  section_title: string;
  chart_spec: Record<string, unknown>;
  chart_svg?: string | null;
  data_total?: number | null;
  row_count: number;
  narrative?: string | null;
}

export interface Report {
  report_id: string;
  title: string;
  prompt: string;
  summary?: string | null;
  status: string;
  created_at: string;
  sections: ReportSection[];
  warnings: string[];
}

export interface ReportSummary {
  id: string;
  title: string;
  created_at: string;
  section_count: number;
}

export function generateReport(
  prompt: string,
  maxSections = 3,
): Promise<Report> {
  return request<Report>("/reports/generate", {
    method: "POST",
    body: { prompt, max_sections: maxSections },
  });
}

export function listReports(): Promise<{ reports: ReportSummary[]; count: number }> {
  return request<{ reports: ReportSummary[]; count: number }>("/reports");
}

export function getReport(reportId: string): Promise<Report> {
  return request<Report>(`/reports/${reportId}`);
}

/** Re-run a persisted report's pipeline on its stored prompt (Phase 19). */
export function regenerateReport(reportId: string): Promise<Report> {
  return request<Report>(`/reports/${reportId}/regenerate`, { method: "POST" });
}

export interface ReportSchedule {
  report_id: string;
  frequency: "hourly" | "daily" | "weekly" | "monthly";
  enabled: boolean;
  next_run_at: string;
  last_run_at?: string | null;
  last_error?: string | null;
}

export function scheduleReport(
  reportId: string,
  frequency: ReportSchedule["frequency"],
): Promise<ReportSchedule> {
  return request<ReportSchedule>(`/reports/${reportId}/schedule`, {
    method: "POST",
    body: { frequency },
  });
}

export function getReportSchedule(reportId: string): Promise<ReportSchedule> {
  return request<ReportSchedule>(`/reports/${reportId}/schedule`);
}

export function unscheduleReport(reportId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/reports/${reportId}/schedule`, {
    method: "DELETE",
  });
}

/** Download a report as PDF (returns the raw bytes). */
export async function exportReportPdf(reportId: string): Promise<Blob> {
  const headers: Record<string, string> = {};
  const token = getStoredToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(apiUrl(`reports/${reportId}/pdf`), { headers });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(res.status, error.code ?? "UNKNOWN", error.message ?? "Export failed");
  }
  return res.blob();
}

// --- Dashboards (Phase 18) ---

export interface DashboardSummary {
  id: string;
  title: string;
  description?: string | null;
  created_at: string;
  section_count: number;
}

export interface DashboardSection {
  pin_id: string;
  position: number;
  report_title: string;
  metric_name: string;
  section_title: string;
  chart_spec: Record<string, unknown>;
  chart_svg?: string | null;
  data_total?: number | null;
  row_count: number;
  narrative?: string | null;
}

export interface DashboardDetail {
  dashboard_id: string;
  user_id: string;
  title: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  sections: DashboardSection[];
  warnings: string[];
}

export function createDashboard(
  title: string,
  description?: string,
): Promise<{ dashboard_id: string; title: string; created_at: string }> {
  return request("/dashboards", { method: "POST", body: { title, description } });
}

export function listDashboards(): Promise<{
  dashboards: DashboardSummary[];
  count: number;
}> {
  return request<{ dashboards: DashboardSummary[]; count: number }>("/dashboards");
}

export function getDashboard(dashboardId: string): Promise<DashboardDetail> {
  return request<DashboardDetail>(`/dashboards/${dashboardId}`);
}

export function deleteDashboard(dashboardId: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/dashboards/${dashboardId}`, { method: "DELETE" });
}

export function pinSection(
  dashboardId: string,
  reportId: string,
  sectionPosition: number,
): Promise<{ pin_id: string; position: number }> {
  return request(`/dashboards/${dashboardId}/sections`, {
    method: "POST",
    body: { report_id: reportId, section_position: sectionPosition },
  });
}

export function unpinSection(
  dashboardId: string,
  pinId: string,
): Promise<{ status: string }> {
  return request(`/dashboards/${dashboardId}/sections/${pinId}`, { method: "DELETE" });
}

// --- Health ---

export function healthCheck(): Promise<{ status: string; version: string }> {
  return request("/health");
}
