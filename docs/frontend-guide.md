# Frontend Guide

> Next.js 15 App Router, TypeScript 5.9, Tailwind CSS v4, shadcn/ui components.
>
> **Guide status:** rewritten after the UX refactor Tasks 1–3. It will be updated again as refactor Phases 1–4 land.

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript 5.9 (strict) |
| Styling | Tailwind CSS v4 with CSS `@theme` tokens |
| Components | shadcn/ui (Radix UI primitives) |
| Validation | Zod 3.24 |
| Icons | lucide-react |
| Markdown | react-markdown (remark-gfm, rehype-raw, rehype-sanitize) |

### Tailwind v4 `@theme` tokens

**File:** `frontend/src/app/globals.css`

Tailwind v4 is configured through CSS only. The file imports `tailwindcss` and declares a single `@theme` block with the brand scale plus semantic aliases.

```css
@import "tailwindcss";

@theme {
  --color-brand-50: #eef2ff;
  --color-brand-100: #e0e7ff;
  --color-brand-200: #c7d2fe;
  --color-brand-300: #91a7ff;
  --color-brand-400: #748ffc;
  --color-brand-500: #6366f1;
  --color-brand-600: #4c6ef5;
  --color-brand-700: #4263eb;
  --color-brand-800: #364fc7;
  --color-brand-900: #2b3a9e;

  --color-surface: #ffffff;
  --color-surface-muted: #f9fafb;
  --color-border: #e5e7eb;
  --color-border-strong: #d1d5db;
  --color-text-muted: #6b7280;
  --color-ring: var(--color-brand-600);
}
```

---

## Project Structure

```
frontend/src/
├── app/
│   ├── globals.css              ← Tailwind v4 import + @theme tokens
│   ├── layout.tsx               ← RootLayout (metadata, AuthProvider)
│   ├── page.tsx                 ← Landing page (dark hero)
│   ├── login/
│   │   └── page.tsx             ← Login page (LoginForm → redirects to /chat)
│   └── (app)/                   ← Workspace route group (no URL prefix)
│       ├── layout.tsx           ← AuthGuard + AppShell wrapper
│       ├── chat/
│       │   └── page.tsx         ← ChatView
│       ├── explore/
│       │   └── page.tsx         ← ExploreView
│       ├── reports/
│       │   └── page.tsx         ← ReportsView
│       ├── dashboards/
│       │   └── page.tsx         ← DashboardsView
│       ├── wiki/
│       │   └── page.tsx         ← WikiView
│       └── settings/
│           └── page.tsx         ← SettingsView
│   └── admin/                   ← Platform superuser portal
│       ├── layout.tsx           ← AuthGuard + PlatformAdminGuard
│       ├── page.tsx             ← Admin overview stats
│       ├── tenants/
│       │   ├── page.tsx         ← Tenant list + provision
│       │   └── [id]/page.tsx    ← Tenant detail / users / LLM
│       ├── admins/
│       │   └── page.tsx         ← Superuser grants
│       └── audit/
│           └── page.tsx         ← Admin audit log
├── components/
│   ├── admin/
│   │   └── tenant-llm-panel.tsx ← BYOK LLM panel for a tenant
│   ├── auth/
│   │   ├── auth-provider.tsx    ← AuthProvider + AuthGuard + PlatformAdminGuard
│   │   └── login-form.tsx       ← Email/password sign-in form
│   ├── charts/
│   │   └── chart-card.tsx       ← ChartCard + ChartGrid
│   ├── chat/
│   │   └── chat-view.tsx        ← Full ChatView with SSE consumption
│   ├── dashboards/
│   │   └── dashboards-view.tsx  ← Dashboard list + builder
│   ├── explore/
│   │   └── explore-view.tsx     ← Metric catalog + native query builder
│   ├── layout/
│   │   ├── app-shell.tsx        ← Persistent workspace sidebar + user card
│   │   └── page-header.tsx      ← Shared in-page header component
│   ├── reports/
│   │   └── reports-view.tsx     ← Multi-chart report workbench
│   ├── settings/
│   │   ├── llm-provider.tsx     ← BYOK LLM provider settings
│   │   ├── settings-view.tsx    ← Profile / password / users / LLM
│   │   └── users-admin.tsx      ← Shared tenant user management table
│   ├── wiki/
│   │   └── wiki-view.tsx        ← Tenant knowledge base editor
│   └── ui/                      ← 12 shadcn/ui primitives
├── lib/
│   ├── api-client.ts            ← Centralized API client with JWT + SSE
│   ├── auth-storage.ts          ← localStorage helpers (genbi_token / genbi_user)
│   ├── shadcn.ts                ← cn() utility (clsx + twMerge) only
│   └── validators.ts            ← Zod schemas with inferred types
└── types/
    └── chart.ts                 ← ChartAssemblyInput, ChartBackend, ChartOutputFormat
```

---

## API Client

**File:** `src/lib/api-client.ts`

Centralized fetch wrapper. All backend communication routes through this file.

### Core Request Function

```typescript
async function request<T>(path: string, options: RequestOptions = {}): Promise<T>
```

- Sets `Content-Type: application/json`
- Attaches JWT from `auth-storage` (`genbi_token` key)
- Throws `ApiError(status, code, message)` on non-OK responses
- Base URL: `NEXT_PUBLIC_API_URL` or `http://localhost:8000/api/v1`
- Relative bases are resolved same-origin for the proxy config; absolute bases are origin-pinned to prevent open redirects

### `ApiError` Class

```typescript
class ApiError extends Error {
  status: number;
  code: string;
  message: string;
}
```

### Exported Functions

```typescript
// Chat
streamChat(req: ChatRequest, onEvent, onError): AbortController          // POST /chat/stream (SSE)
sendFeedback(sessionId, score): Promise<{ status; session_id; score }>   // POST /chat/feedback

// Charts
renderChart(req: ChartRenderRequest): Promise<ChartRenderResponse>       // POST /charts/render

// Metrics
listMetrics(): Promise<MetricListResponse>                               // GET /metrics/list
queryMetrics(req: MetricQueryRequest): Promise<MetricQueryResponse>      // POST /metrics/query

// Conversations
listConversations(): Promise<{ conversations; count }>                   // GET /conversations
listConversationMessages(conversationId): Promise<{ messages; count }>   // GET /conversations/:id/messages

// Reports
generateReport(prompt, maxSections): Promise<Report>                     // POST /reports/generate
listReports(): Promise<{ reports; count }>                               // GET /reports
getReport(reportId): Promise<Report>                                     // GET /reports/:id
regenerateReport(reportId): Promise<Report>                              // POST /reports/:id/regenerate
scheduleReport(reportId, frequency): Promise<ReportSchedule>             // POST /reports/:id/schedule
getReportSchedule(reportId): Promise<ReportSchedule>                     // GET /reports/:id/schedule
unscheduleReport(reportId): Promise<{ status }>                          // DELETE /reports/:id/schedule
exportReportPdf(reportId): Promise<Blob>                                 // GET /reports/:id/pdf

// Dashboards
createDashboard(title, description?): Promise<{ dashboard_id; title; created_at }>  // POST /dashboards
listDashboards(): Promise<{ dashboards; count }>                                      // GET /dashboards
getDashboard(dashboardId): Promise<DashboardDetail>                                   // GET /dashboards/:id
deleteDashboard(dashboardId): Promise<{ status }>                                     // DELETE /dashboards/:id
pinSection(dashboardId, reportId, sectionPosition): Promise<{ pin_id; position }>     // POST /dashboards/:id/sections
unpinSection(dashboardId, pinId): Promise<{ status }>                                 // DELETE /dashboards/:id/sections/:pinId

// Admin (platform superuser)
getAdminStats(): Promise<PlatformStats>                                  // GET /admin/stats
listTenantsAdmin(): Promise<{ tenants; count }>                          // GET /admin/tenants
provisionTenant(body): Promise<ProvisionResult>                          // POST /admin/tenants
getTenantDetail(tenantId): Promise<TenantDetail>                         // GET /admin/tenants/:id
updateTenantAdmin(tenantId, body): Promise<TenantDetail>                 // PATCH /admin/tenants/:id
decommissionTenant(tenantId, force): Promise<{ status }>                 // DELETE /admin/tenants/:id
listSuperadmins(): Promise<SuperadminGrant[]>                            // GET /admin/admins
grantSuperadmin(body): Promise<SuperadminGrant>                          // POST /admin/admins
revokeSuperadmin(userId): Promise<{ status }>                            // DELETE /admin/admins/:id
listAdminAudit(limit?): Promise<AdminAuditEntry[]>                       // GET /admin/audit
getTenantLLM(tenantId, days?): Promise<TenantLLM>                        // GET /admin/tenants/:id/llm
putTenantLLM(tenantId, body): Promise<LLMProviderConfig>                 // PUT /admin/tenants/:id/llm
patchTenantLLMStatus(tenantId, status): Promise<LLMProviderConfig>       // PATCH /admin/tenants/:id/llm

// Tenant users + self-service
getMe(): Promise<User>                                                   // GET /auth/me
changePassword(currentPassword, newPassword): Promise<{ status }>        // POST /auth/change-password
listUsers(tenantId?): Promise<{ users; count }>                          // GET /users
createUser(body): Promise<TenantUserRow>                                 // POST /users
updateUser(userId, body, tenantId?): Promise<TenantUserRow>              // PATCH /users/:id
deleteUser(userId, tenantId?): Promise<{ status }>                       // DELETE /users/:id
resetUserPassword(userId, password, tenantId?): Promise<{ status }>      // POST /users/:id/reset-password

// Wiki
listWikiPages(): Promise<WikiPageSummary[]>                              // GET /wiki
getWikiPage(slug): Promise<WikiPage>                                     // GET /wiki/:slug
upsertWikiPage(slug, body): Promise<WikiPage>                            // PUT /wiki/:slug
deleteWikiPage(slug): Promise<{ status }>                                // DELETE /wiki/:slug
getWikiHistory(slug): Promise<WikiRevision[]>                            // GET /wiki/:slug/history
restoreWikiPage(slug, version): Promise<WikiPage>                        // POST /wiki/:slug/restore/:version
searchWiki(q, topK?): Promise<WikiSearchHit[]>                           // GET /wiki/search

// BYOK LLM providers
getLLMConfig(): Promise<LLMProviderConfig>                               // GET /settings/llm
saveLLMConfig(body): Promise<LLMProviderConfig>                          // PUT /settings/llm
validateLLMConfig(body): Promise<{ status; provider }>                    // POST /settings/llm/validate
setLLMStatus(status): Promise<LLMProviderConfig>                         // PATCH /settings/llm
deleteLLMConfig(): Promise<{ status; provider }>                         // DELETE /settings/llm
```

### `streamChat` — SSE Implementation

Uses `fetch` with an `AbortController` signal, reads the response body with `ReadableStream`:
- Decodes chunks with `TextDecoder`
- Splits on `\n`
- Strips `data: ` prefix
- Parses JSON via `JSON.parse`
- Calls `onEvent(parsed)` for each event
- Invalid lines are silently skipped
- Returns `AbortController` for cancellation

---

## Zod Validators

**File:** `src/lib/validators.ts`

All schemas use `z.object(...)` with inferred types:

| Schema | Key Validations |
|---|---|
| `ChatRequestSchema` | `query: z.string().min(1).max(2000)`, optional `conversation_id: z.string().uuid()`, optional `confirm_large_query: z.boolean()` |
| `SSEEventSchema` | `event: z.enum(["start","intent","sql","validation","data","chart","narrative","done"])` plus optional fields for plan, SQL, chart spec, image, SVG, narrative, warnings, etc. |
| `MetricListResponseSchema` | Array of metrics with name, title, description, metric_type, cube_name, measure_name, dimensions, time_dimensions |
| `MetricQueryResponseSchema` | data, annotation, total, query, latency_ms, cached |
| `LoginRequestSchema` | `email: z.string().email()`, `password: z.string().min(6)` |
| `LoginResponseSchema` | access_token, token_type, user |
| `TenantProvisionSchema` | name, slug regex, admin_email, seed_sample_data |
| `LLMConfigSchema` | provider, api_key, base_url, reasoning_model, fast_model, embedding_model |

---

## App Shell and Page Header

### `AppShell` (`src/components/layout/app-shell.tsx`)

The persistent workspace layout introduced in Phase 27b.

- Wraps every route under `(app)` via `app/(app)/layout.tsx`
- Dark left sidebar (desktop) / drawer (mobile) with workspace nav: **Chat**, **Explore**, **Reports**, **Dashboards**, **Wiki**
- Account section with **Settings** and **Admin portal** (only for `platform_admin`)
- User card at the bottom showing initials, name/email, and logout
- Mobile hamburger top bar
- Centralizes workspace navigation, user identity, and logout

### `PageHeader` (`src/components/layout/page-header.tsx`)

Shared in-page header for workspace views:
- Icon + title + description on the left
- Arbitrary actions slot on the right
- Rendered as the first child of a view's content column

---

## Chat View (SSE Streaming)

**File:** `src/components/chat/chat-view.tsx`

The main application component. Full-height flex layout inside the AppShell content column.

### State
```typescript
messages: ChatMessage[];     // User + assistant message pairs
loading: boolean;             // In-flight request indicator
abortRef: AbortController;   // SSE cancellation
```

### Pipeline Progress (Stage Badges)

A row of `Badge` components shows real-time pipeline progress: **Intent** → **SQL** → **Validated** → **Results** → **Chart** → **Insight** → **Done**. A pulsing badge appears while the corresponding stage is streaming.

### SSE Event Handling

`updateMessageStage(msg, event)` incrementally populates the assistant message:

| Event | Populates |
|---|---|
| `sql` | `msg.sql` |
| `validation` | `msg.sql` = `validated_sql` |
| `data` | Row count, data preview |
| `chart` | `msg.chartSpec`, `msg.chartSvg`, `msg.chartBase64` |
| `narrative` | `msg.narrative` |
| `done` | Finalizes content, sets `streaming: false` |

### Layout

- No standalone top navbar (navigation moved to `AppShell` sidebar)
- Messages area with scrolling container, empty state suggestions, user/assistant message styling
- Input bar at the bottom with Send/Cancel
- Feedback thumbs on completed assistant messages (`sendFeedback`)

---

## Chart Card

**File:** `src/components/charts/chart-card.tsx`

**Props:** `spec: ChartAssemblyInput`, `imageBase64?: string`, `svg?: string`, `title?: string`, `onDownload?: () => void`

Renders within a bordered `Card`:
- **Header:** chart type label + "Flint" badge, format toggle (SVG/PNG), Download button
- **Body:** Conditionally renders SVG via `dangerouslySetInnerHTML` with `class="vis-flint-chart"`, Base64 PNG `<img>`, or a placeholder while streaming

**`ChartGrid`:** Responsive 1-column (mobile) / 2-column (desktop) grid layout for multiple charts.

---

## Auth Provider

**File:** `src/components/auth/auth-provider.tsx`

### Auth Flow

```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  logout(): void;
  isAuthenticated: boolean;
}
```

- **Login:** POST to `/auth/login`, stores `genbi_token` + `genbi_user` in `localStorage`
- **Session restoration:** On mount, reads from `localStorage`. If parsing fails, clears both.
- **Loading guard:** While `loading` is true, renders bouncing dots.
- **User object** includes `platform_admin` flag minted at login.

### `AuthGuard` Component

Wraps protected pages. Shows:
- Loading: bouncing dots animation
- Unauthenticated: `router.replace("/login")` redirect
- Authenticated: children

### `PlatformAdminGuard` Component

Wraps `/admin/*`. Adds a second gate on `user.platform_admin` and shows a "privileges required" message otherwise. The backend re-verifies the grant on every `/admin` call.

### `LoginForm` Component

**File:** `src/components/auth/login-form.tsx` — extracted, reusable email/password form with `onSuccess` callback. Used by the `/login` page, which navigates to `/chat` after a successful sign-in.

---

## UI Components (shadcn/ui)

**File:** `src/components/ui/*.tsx` | **Utility:** `cn()` from `@/lib/shadcn`

Radix-based components use Tailwind CSS with class-variance-authority (CVA) for variants; plain-HTML and `react-markdown` components are noted in the table below.

| Component | Primitive | Variants / Notes |
|---|---|---|
| `Avatar` | `@radix-ui/react-avatar` | Root (40x40, rounded-full), Image, Fallback (gray bg, centered initials) |
| `Badge` | Plain div | `default` (brand), `secondary`, `destructive`, `outline`, `success`, `warning`. Pill shape, text-xs |
| `Button` | `@radix-ui/react-slot` (asChild) | `default` (brand+shadow), `destructive`, `outline`, `secondary`, `ghost`, `link`. Sizes: `default`, `sm`, `lg`, `icon` |
| `Card` | Plain HTML | Compound: Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter. Rounded-xl border shadow |
| `Dialog` | `@radix-ui/react-dialog` | Overlay (bg-black/50), Content (centered, rounded-xl), with X close button |
| `DropdownMenu` | `@radix-ui/react-dropdown-menu` | Content (z-50, min-w-8rem), Items with keyboard shortcuts, Separator |
| `Input` | Plain `<input>` | h-10, rounded-lg border, focus ring-brand-600 |
| `MarkdownText` | `react-markdown` | Shared markdown renderer for chat narratives and wiki content; allows `data:image/` URIs |
| `Separator` | Plain div | Horizontal (`h-px w-full`) or Vertical |
| `Skeleton` | Plain div | `animate-pulse rounded-md bg-gray-200` |
| `Tabs` | `@radix-ui/react-tabs` | List (inline-flex, bg-gray-100), Trigger (pill, active=white bg+shadow), Content |
| `Tooltip` | `@radix-ui/react-tooltip` | Content (bg-gray-900, text-xs, white text, shadow-md) |

### shadcn.cn Utility

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

---

## Type Definitions

**File:** `src/types/chart.ts`

```typescript
export interface ChartAssemblyInput {
  chartType: string;
  encodings: Record<string, { field: string }>;
  baseSize: { width: number; height: number };
  semantic_types?: Record<string, "Category" | "Quantity" | "Temporal">;
  data: {
    values?: Record<string, unknown>[];
    url?: string;
  };
}

export type ChartBackend = "vegalite" | "echarts" | "chartjs";
export type ChartOutputFormat = "png" | "svg";
```

---

## Pages

### `layout.tsx` — Root Layout

- HTML metadata: title `"GenBI — Generative Business Intelligence"`
- Applies `globals.css`, wraps children in `AuthProvider`
- Body: `min-h-screen bg-gray-50 text-gray-900 antialiased`

### `page.tsx` — Landing Page

Dark full-page hero with feature cards. The CTA routes to `/chat` when signed in and `/login` when signed out.

### `login/page.tsx` — Login Page

Redirects to `/chat` if already authenticated; otherwise renders `LoginForm`, which navigates to `/chat` on success.

### `(app)/layout.tsx` — Workspace Layout

Wraps workspace pages in a single `AuthGuard` and the shared `AppShell`. Pages inside this group no longer carry their own guards or top navbars.

### `(app)/chat/page.tsx` — Chat Page

Renders `ChatView`. Navigation is provided by the AppShell sidebar.

### `(app)/explore/page.tsx` — Explore Page

Wraps `ExploreView`. The semantic-layer workbench:

- **Catalog**: metrics from `GET /metrics/list` as clickable cards
- **Query builder**: native `<select>` elements for measure, group-by dimension, optional time granularity, and row limit
- **Run**: `POST /metrics/query` → results table + bar chart rendered via `ChartCard`
- Empty results show an RLS-aware hint

### `(app)/reports/page.tsx` — Reports Page

Wraps `ReportsView`. The multi-chart report workbench:

- **Generator**: prompt input + section-count select (2–4) + Generate → `POST /reports/generate`
- **Sidebar**: past reports from `GET /reports`; select loads via `GET /reports/{id}`
- **Report display**: title + summary + badges, per-section `ChartCard`s, warnings panel
- Scheduling, regeneration, and PDF export are supported

### `(app)/dashboards/page.tsx` — Dashboards Page

Wraps `DashboardsView`. Boards of pinned report sections:

- Create/list/delete dashboards via `/dashboards`
- Pin/unpin report sections into a board
- Render persisted SVG charts

### `(app)/wiki/page.tsx` — Wiki Page

Wraps `WikiView`. Tenant knowledge base:

- List pages, edit markdown, set parent pages
- Version history and restore
- Semantic search over wiki chunks

### `(app)/settings/page.tsx` — Settings Page

Wraps `SettingsView`. Four sections:

- **Profile** from `GET /auth/me` (email, tenant, roles, platform-superuser badge)
- **Change password** (`POST /auth/change-password`)
- **AI provider / BYOK** (`LLMProviderSettings`, tenant admins only)
- **Tenant users** (`UsersAdmin`, tenant admins only) — create, role select, enable/disable, reset password, delete with confirm

### `admin/layout.tsx` — Admin Portal Layout

Wraps `/admin/*` in `AuthGuard` + `PlatformAdminGuard`. Own sidebar nav: **Overview**, **Tenants**, **Superusers**, **Audit log**. A "Back to GenBI" link returns to `/chat`.

### `admin/page.tsx` — Platform Overview

Stat cards from `GET /admin/stats`: tenants, users, LLM calls/tokens (24h), platform superusers.

### `admin/tenants/page.tsx` — Tenant List

Lists tenants, shows status badges, provisions new tenants with a one-time generated password.

### `admin/tenants/[id]/page.tsx` — Tenant Detail

Single-tenant management:

- Suspend / activate / rename / decommission
- Counters, recent admin actions
- User management via `UsersAdmin` with `?tenant_id=` superuser path
- BYOK LLM panel (`TenantLLMPanel`)
- JSON tenant settings editor

### `admin/admins/page.tsx` — Superuser Grants

Lists `platform_admins` grants with history, grants/revokes by email.

### `admin/audit/page.tsx` — Admin Audit Log

Append-only control-plane audit feed from `GET /admin/audit`. Client-side filters for actor and action/target.

---

## Build Commands

```bash
pnpm dev          # Next.js dev server (port 3000)
pnpm build        # Production build
pnpm start        # Start production server
pnpm lint         # ESLint
pnpm typecheck    # tsc --noEmit
pnpm format       # Prettier
```
