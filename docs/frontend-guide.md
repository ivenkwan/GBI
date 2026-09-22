# Frontend Guide

> Next.js 15 App Router, TypeScript 5.9, Tailwind CSS v4, shadcn/ui components.
>
> **Guide status:** current through the frontend UX refactor (Tasks 1–34): `@theme` tokens, the shared primitive set, the unified `(app)` shell (including the admin pages), and the decomposed chat architecture are all landed.

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
│   ├── error.tsx                ← Root error boundary (Alert + retry)
│   ├── not-found.tsx            ← 404 page
│   ├── login/
│   │   └── page.tsx             ← Login page (LoginForm → redirects to /chat)
│   └── (app)/                   ← Workspace route group (no URL prefix)
│       ├── layout.tsx           ← AuthGuard + AppShell wrapper (every workspace page)
│       ├── error.tsx            ← In-shell error boundary
│       ├── loading.tsx          ← In-shell route loading state (Loader)
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
│       ├── settings/
│       │   └── page.tsx         ← SettingsView (tabs)
│       └── admin/               ← Platform superuser pages (render inside AppShell)
│           ├── layout.tsx       ← PlatformAdminGuard
│           ├── page.tsx         ← Admin overview stats
│           ├── tenants/
│           │   ├── page.tsx     ← Tenant list (DataTable) + provision dialog
│           │   └── [id]/page.tsx← Tenant detail / users / LLM
│           ├── admins/
│           │   └── page.tsx     ← Superuser grants (DataTable)
│           └── audit/
│               └── page.tsx     ← Admin audit log (DataTable + client filters)
├── components/
│   ├── admin/
│   │   └── tenant-llm-panel.tsx ← BYOK LLM panel + spend DataTable for a tenant
│   ├── auth/
│   │   ├── auth-provider.tsx    ← AuthProvider + AuthGuard + PlatformAdminGuard
│   │   └── login-form.tsx       ← Email/password sign-in form
│   ├── charts/
│   │   └── chart-card.tsx       ← ChartCard + ChartGrid
│   ├── chat/                    ← Decomposed ChatView (see Chat View section)
│   │   ├── chat-view.tsx        ← Thin composition root (hooks + components)
│   │   ├── chat-types.ts        ← ChatMessage type + id helpers
│   │   ├── conversation-sidebar.tsx
│   │   ├── message-list.tsx
│   │   ├── assistant-message-card.tsx
│   │   ├── stage-badges.tsx
│   │   ├── sql-block.tsx
│   │   ├── feedback-thumbs.tsx
│   │   ├── large-query-confirm.tsx
│   │   └── chat-input.tsx
│   ├── dashboards/
│   │   └── dashboards-view.tsx  ← Dashboard list + builder
│   ├── explore/
│   │   └── explore-view.tsx     ← Metric catalog + native query builder
│   ├── layout/
│   │   ├── app-shell.tsx        ← Persistent workspace sidebar + user card
│   │   ├── page-container.tsx   ← Centered max-w-5xl scroll container
│   │   └── page-header.tsx      ← Shared in-page header component
│   ├── llm/
│   │   └── llm-provider-form.tsx← Shared BYOK form ("self" / "tenant" modes)
│   ├── reports/
│   │   └── reports-view.tsx     ← Multi-chart report workbench
│   ├── settings/
│   │   ├── llm-provider.tsx     ← BYOK section wrapper (self mode) for /settings
│   │   ├── settings-view.tsx    ← Profile / password / users / AI-provider tabs
│   │   └── users-admin.tsx      ← Shared tenant user management table
│   ├── wiki/
│   │   └── wiki-view.tsx        ← Tenant knowledge base editor
│   └── ui/                      ← 19 shared primitives (see UI Components)
├── hooks/
│   ├── use-chat-stream.ts       ← Chat message state + SSE streaming lifecycle
│   ├── use-conversations.ts     ← Conversation list + active conversation id
│   └── use-selection-param.ts   ← Two-way bind a selection id to a URL param
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

### The unified `(app)` group

Every authenticated page — Chat, Explore, Reports, Dashboards, Wiki, Settings, **and the platform admin pages** — lives under `app/(app)/` and renders inside the shared `AppShell` behind a single `AuthGuard` (`app/(app)/layout.tsx`). There is no separate admin portal layout: `app/(app)/admin/layout.tsx` adds only a `PlatformAdminGuard`, so superusers see admin pages in the same shell with the same sidebar. The group also carries an in-shell `error.tsx` boundary and a `loading.tsx` route state; a root `app/error.tsx` and `app/not-found.tsx` cover the rest.

### `AppShell` (`src/components/layout/app-shell.tsx`)

The persistent workspace layout.

- Wraps every route under `(app)` via `app/(app)/layout.tsx`
- Dark left sidebar (desktop) / drawer (mobile) with workspace nav: **Chat**, **Explore**, **Reports**, **Dashboards**, **Wiki**
- Account section with **Settings**; a **Platform** section (**Overview**, **Tenants**, **Superusers**, **Audit log**) renders only when `user.platform_admin` is true
- Active nav item uses the brand token (`bg-brand-600`)
- User card at the bottom showing initials, name/email, and a dropdown with Settings + sign out
- Mobile hamburger top bar opens the nav drawer
- Centralizes workspace navigation, user identity, and logout; pages mount once and navigation does not remount the shell

### `PageHeader` (`src/components/layout/page-header.tsx`)

Shared in-page header for workspace views:
- Icon + title + description on the left
- Arbitrary actions slot on the right
- Rendered as the first child of a view's content column

### `PageContainer` (`src/components/layout/page-container.tsx`)

Centered `max-w-5xl` scroll container used by the form-style pages (settings, admin) below their `PageHeader`.

---

## Chat View (SSE Streaming)

**Composition root:** `src/components/chat/chat-view.tsx` — a thin wiring layer with no fetch or stream logic of its own. State lives in hooks; rendering lives in presentational components.

### Hooks (`src/hooks/`)

| Hook | Owns |
|---|---|
| `useConversations()` | Conversation list, active conversation id, list error, `refresh` / `selectConversation` / `startNewChat` / `handleServerAssignedId` |
| `useChatStream({ conversationId, onConversationId, onTurnComplete })` | `messages`, `loading`, `inputError`, the SSE `AbortController`, and the actions `send`, `confirmLargeQuery`, `retry`, `cancel`, `loadHistory`, `reset`, `setFeedback` |
| `useSelectionParam(param)` | Two-way binds the active conversation id to the `?conv=` URL param (deep links, refresh restore, back/forward) |

`send(input)` validates against `ChatRequestSchema` first — invalid input keeps the typed text and surfaces a hint under the input. `confirmLargeQuery` reuses the pending turn's bubble (no duplicate user message). `setFeedback` posts the resulting score (clicking the active thumb clears to 0) and rolls back on failure. Stream failures surface a retryable error `Alert`.

### Components (`src/components/chat/`)

| Component | Role |
|---|---|
| `ConversationSidebar` | Conversation list + "New chat", rendered in a desktop `<aside>` and in a mobile `Sheet` ("Conversations" toggle below `md`) |
| `MessageList` | Scroll container, empty-state suggestions, auto-scroll; maps messages to cards |
| `AssistantMessageCard` | One assistant turn: stage badges, streaming skeleton, `SqlBlock`, `ChartCard`, narrative `MarkdownText`, warnings `Alert`, `FeedbackThumbs`, `LargeQueryConfirm` |
| `StageBadges` | Pipeline progress badges: **Intent** → **SQL** → **Validated** → **Results** → **Chart** → **Insight** → **Done**; pulsing badge while a stage streams |
| `SqlBlock` | Dark terminal-style SQL panel with copy button |
| `FeedbackThumbs` | Thumbs up/down on completed messages (`sendFeedback`) |
| `LargeQueryConfirm` | In-bubble confirm for `confirmation_required` turns (row estimate + confirm/cancel) |
| `ChatInput` | Bottom input bar with Send/Cancel and the validation hint slot |
| `chat-types.ts` | `ChatMessage` type + `newMessageId` helper |

### SSE Event Handling

`updateMessageStage(msg, event)` (inside `useChatStream`) incrementally populates the assistant message:

| Event | Populates |
|---|---|
| `sql` | `msg.sql` |
| `validation` | `msg.sql` = `validated_sql` |
| `data` | Row count, data preview |
| `chart` | `msg.chartSpec`, `msg.chartSvg`, `msg.chartBase64` |
| `narrative` | `msg.narrative` |
| `done` | Finalizes content, sets `streaming: false`; `confirmation_required` sets `needsConfirm` + `rowEstimate` |

### Layout

- No standalone top navbar (navigation is the `AppShell` sidebar)
- Desktop conversations `<aside>` at `md` and up; below `md` a "Conversations" toggle opens the same sidebar in a `Sheet`
- Messages area with scrolling container, empty state suggestions, user/assistant message styling
- Input bar at the bottom with Send/Cancel

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
- **Loading guard:** While `loading` is true, renders `<Loader fullScreen />`.
- **User object** includes `platform_admin` flag minted at login.

### `AuthGuard` Component

Wraps protected pages. Shows:
- Loading: `<Loader fullScreen />`
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
| `Alert` | Plain div + CVA | `error` (default), `success`, `warning`. Icon + optional title/dismiss/action; `role="alert"`. The only place `bg-red-50`/`bg-green-50` banners live |
| `Avatar` | `@radix-ui/react-avatar` | Root (40x40, rounded-full), Image, Fallback (gray bg, centered initials) |
| `Badge` | Plain div | `default` (brand), `secondary`, `destructive`, `outline`, `success`, `warning`. Pill shape, text-xs |
| `Button` | `@radix-ui/react-slot` (asChild) | `default` (brand+shadow), `destructive`, `outline`, `secondary`, `ghost`, `link`. Sizes: `default`, `sm`, `lg`, `icon` |
| `Card` | Plain HTML | Compound: Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter. Rounded-xl border shadow |
| `ConfirmDialog` | `Dialog` | Shared confirm/submit modal: `confirmLabel`, `confirmVariant` (`destructive`/`default`), optional `requireText` typed-confirmation, `busy`, form children slot |
| `DataTable` | Plain `<table>` | Generic `<T>` columns/`render` API with `keyField`, `emptyText`, `loading` (renders `Loader`), right/center alignment. The only hand-built table in the app besides `MarkdownText` |
| `Dialog` | `@radix-ui/react-dialog` | Overlay (bg-black/50), Content (centered, rounded-xl), with X close button |
| `DropdownMenu` | `@radix-ui/react-dropdown-menu` | Content (z-50, min-w-8rem), Items with keyboard shortcuts, Separator |
| `EmptyState` | Plain div | `card` / `inline` / `centered` variants; optional lucide icon, title, description, action slot |
| `Input` | Plain `<input>` | h-10, rounded-lg border, focus ring-brand-600 |
| `Loader` | Plain div | Three brand-colored bouncing dots; `size` (`sm`/`md`/`lg`), `fullScreen`, `label`. The only `animate-bounce` in the app |
| `MarkdownText` | `react-markdown` | Shared markdown renderer for chat narratives and wiki content; allows `data:image/` URIs |
| `Separator` | Plain div | Horizontal (`h-px w-full`) or Vertical |
| `Sheet` | `@radix-ui/react-dialog` | Side-anchored panel (left/right) hosting in-view sidebar lists below their breakpoint; focus trap + Escape via Radix |
| `SidebarList` | Plain div | Shared "label + '+' + selectable rows" sidebar block (`SidebarListItem`: id/label/secondary); used in `<aside>` on desktop and `Sheet` on mobile |
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

### `error.tsx` / `not-found.tsx` — Root Boundaries

`app/error.tsx` is the root error boundary (centered `Alert` + Try again / back-home buttons); `app/not-found.tsx` is the 404 page. Inside the shell, `(app)/error.tsx` and `(app)/loading.tsx` provide the same treatment without dropping the sidebar.

### `(app)/layout.tsx` — Workspace Layout

Wraps every workspace page (including `/admin/*`) in a single `AuthGuard` and the shared `AppShell`. Pages inside this group no longer carry their own guards or top navbars. `(app)/error.tsx` renders an in-shell `Alert` with retry; `(app)/loading.tsx` renders a `Loader` during route transitions.

### `(app)/chat/page.tsx` — Chat Page

Renders `ChatView`. Navigation is provided by the AppShell sidebar.

### `(app)/explore/page.tsx` — Explore Page

Wraps `ExploreView`. The semantic-layer workbench:

- **Catalog**: metrics from `GET /metrics/list` as clickable cards
- **Query builder**: native `<select>` elements for measure, group-by dimension, optional time granularity, and row limit
- **Run**: `POST /metrics/query` → results `DataTable` + bar chart rendered via `ChartCard`
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

Wraps `SettingsView`. A `Tabs` layout:

- **Profile** from `GET /auth/me` (email, tenant, roles, platform-superuser badge)
- **Password** (`POST /auth/change-password`)
- **Users** (tenant admins only) — `UsersAdmin` DataTable: create, role select, enable/disable, reset password, delete with `ConfirmDialog`
- **AI Provider** (tenant admins only) — `LLMProviderSettings`, the shared `LLMProviderForm` in `self` mode (BYOK save / live validate / revert-to-platform)

### `(app)/admin/layout.tsx` — Admin Section Layout

Adds only a `PlatformAdminGuard` on top of the workspace shell — the admin pages render inside the same `AppShell`, with the **Platform** nav section visible to superusers. The backend re-verifies the grant on every `/admin` call.

### `(app)/admin/page.tsx` — Platform Overview

Stat cards from `GET /admin/stats`: tenants, users, LLM calls/tokens (24h), platform superusers.

### `(app)/admin/tenants/page.tsx` — Tenant List

`DataTable` of tenants (name link, slug, status badge, user count, created date) with a `ConfirmDialog`-based provision flow that shows the one-time generated password once in a success `Alert`.

### `(app)/admin/tenants/[id]/page.tsx` — Tenant Detail

Single-tenant management:

- Suspend / activate / rename / decommission (typed-slug `ConfirmDialog`)
- Counters, recent admin actions list
- User management via `UsersAdmin` with the `?tenant_id=` superuser path
- BYOK LLM panel (`TenantLLMPanel`): shared `LLMProviderForm` in `tenant` mode (force-set) plus the spend-attribution `DataTable` (day × model grain)
- JSON tenant settings editor

### `(app)/admin/admins/page.tsx` — Superuser Grants

`DataTable` of `platform_admins` grants with history; grants/revokes by email.

### `(app)/admin/audit/page.tsx` — Admin Audit Log

Append-only control-plane audit feed from `GET /admin/audit`, rendered as a `DataTable`. Two client-side filter inputs (actor id; action/target) filter the rows before they reach the table.

---

## LLM Provider Form (BYOK)

**File:** `src/components/llm/llm-provider-form.tsx`

One shared implementation of the BYOK LLM key form, in two modes:

- **`self`** — tenant-admin self-service at `/settings` (wrapped by `LLMProviderSettings`). Load/save via `/settings/llm`; includes live Validate (1-token ping) and Revert-to-platform.
- **`tenant`** — platform-admin force-set at `/admin/tenants/[id]` (inside `TenantLLMPanel`, above the spend `DataTable`). Load/save via `/admin/tenants/:id/llm`; no validate ping, no revert.

The key is write-only in both modes: saved state shows `last4` + version only. Section shells, headings, and mode-specific extras live in the wrappers.

---

## Verification

The refactor's exit gates, all expected green with 0 errors:

```bash
cd frontend
pnpm typecheck   # tsc --noEmit
pnpm lint        # eslint .
pnpm build       # production build — every route compiles
```

Consistency sweep (run from `frontend/`; everything must come back CLEAN — a desktop `<aside>` listed by the sidebar check is acceptable only when the same view also renders it in a `Sheet`):

```bash
grep -rn "bg-red-50\|bg-green-50" src/ || echo CLEAN_ALERTS
grep -rn "animate-bounce" src/ | grep -v "ui/loader.tsx" || echo CLEAN_LOADERS
grep -rn "fixed inset-0" src/ --include=*.tsx | grep -v "ui/sheet.tsx\|ui/dialog.tsx\|layout/app-shell.tsx" || echo CLEAN_MODALS
grep -rn "hidden md:flex" src/ --include=*.tsx | grep -v "Sheet\|sheet" || echo CHECK_SIDEBARS
grep -rn "style={{" src/ | grep -i "#[0-9a-f]\{3,6\}\|rgba(" || echo CLEAN_INLINE
grep -rn "<table" src/ --include=*.tsx | grep -v "ui/data-table.tsx\|ui/markdown.tsx" || echo CLEAN_TABLES
```

Accepted remnants: the `Alert` primitive's own variant classes, `bg-red-500` (substring false positive), destructive-hover states, and the feedback thumbs' active colors match the alerts grep; chat/reports/dashboards/wiki sidebars each have a `Sheet` counterpart.

The backend suite (`make verify`) is untouched by the refactor and stays green.

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
