# Frontend Guide

> Next.js 15 App Router, TypeScript 5.9, Tailwind CSS v4, shadcn/ui components.

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript 5.9 (strict) |
| Styling | Tailwind CSS v4 with custom `brand` palette |
| Components | shadcn/ui (Radix UI primitives) |
| Validation | Zod 3.24 |
| Icons | lucide-react |
| Markdown | react-markdown (rehype + remark plugins) |

---

## Project Structure

```
frontend/src/
├── app/
│   ├── globals.css          ← Tailwind directives + brand palette
│   ├── layout.tsx           ← RootLayout (metadata, AuthProvider)
│   ├── page.tsx             ← Landing page (hero + auth-aware CTA)
│   ├── login/
│   │   └── page.tsx         ← Login page (LoginForm → redirects to /chat)
│   ├── chat/
│   │   └── page.tsx         ← Chat page (AuthGuard → ChatView)
│   └── explore/
│       └── page.tsx         ← Explore page (AuthGuard → ExploreView)
├── components/
│   ├── auth/
│   │   ├── auth-provider.tsx    ← AuthProvider + AuthGuard (redirects to /login)
│   │   └── login-form.tsx       ← Email/password sign-in form
│   ├── charts/
│   │   └── chart-card.tsx       ← ChartCard + ChartGrid
│   ├── chat/
│   │   └── chat-view.tsx        ← Full ChatView with SSE consumption
│   ├── explore/
│   │   └── explore-view.tsx     ← Metric catalog + native query builder
│   └── ui/                  ← 11 shadcn/ui primitives
├── lib/
│   ├── api-client.ts        ← Centralized API client with JWT + SSE
│   ├── auth-storage.ts      ← Session keys + localStorage helpers (genbi_token/genbi_user)
│   ├── shadcn.ts            ← cn() utility (clsx + twMerge)
│   └── validators.ts        ← Zod schemas with inferred types
└── types/
    ├── index.ts             ← Shared types
    └── chart.ts             ← ChartAssemblyInput, enums
```

---

## API Client

**File:** `src/lib/api-client.ts`

Centralized fetch wrapper. All backend communication routes through this file.

### Core Request Function

```typescript
async function request<T>(path: string, options: RequestInit = {}): Promise<T>
```

- Sets `Content-Type: application/json`
- Attaches JWT from `auth-storage` (`genbi_token` key)
- Throws `ApiError(status, code, message)` on non-OK responses
- Default base URL: `http://localhost:8000/api/v1`

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
sendChat(req: ChatRequest): Promise<ChatResponse>              // POST /chat
streamChat(req: ChatRequest, onEvent, onError): AbortController  // POST /chat/stream (SSE)
renderChart(req: ChartRenderRequest): Promise<ChartRenderResponse>  // POST /charts/render
listMetrics(): Promise<MetricListResponse>                    // GET /metrics/list (Phase 10)
queryMetrics(req: MetricQueryRequest): Promise<MetricQueryResponse>  // POST /metrics/query (tenant-scoped)
listDatasources(): Promise<{ datasources: DatasourceSummary[]; count: number }>  // GET /datasources
healthCheck(): Promise<{ status: string; version: string }>     // GET /health
```

### `streamChat` — SSE Implementation

Uses `ReadableStream` reader with a line buffer:
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
| `ChatRequestSchema` | `query: z.string().min(1).max(2000)`, optional `conversation_id: z.string().uuid()` |
| `ChatResponseSchema` | All optional except `conversation_id`, `query`, `warnings` |
| `SSEEventSchema` | `event: z.enum(["start","intent","sql","validation","data","chart","narrative","done"])` |
| `ChartAssemblyInputSchema` | `chartType: z.string().min(1)`, `encodings`, `baseSize` (positive ints) |
| `MetricDefinitionSchema` | `metric_type: z.enum([...9 types])` |
| `LoginRequestSchema` | `email: z.string().email()`, `password: z.string().min(6)` |
| `LoginResponseSchema` | `access_token`, `token_type`, `user: { id, email, name, tenant_id, roles }` |

---

## Chat View (SSE Streaming)

**File:** `src/components/chat/chat-view.tsx`

The main application component. Full-height flex layout with:

### State
```typescript
messages: ChatMessage[];    // User + assistant message pairs
loading: boolean;            // In-flight request indicator
abortRef: AbortController;  // SSE cancellation
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

- **Header:** Logo, view toggle ("Chat" / "Metrics"), settings, user avatar, logout
- **Messages area:** Scrolling container. Empty state: centered greeting with three suggestion chips ("Show revenue by region", "Monthly active users trend", "Top 10 customers by value"). User messages: right-aligned, `brand-600` background. Assistant messages: `Card` with stage badges, SQL block (dark terminal style with copy button), chart card, narrative text, amber warning boxes.
- **Input bar:** Fixed-bottom styled `Input` with Send/Cancel button. Disclaimer: "GenBI can make mistakes. Verify important data."

---

## Chart Card

**File:** `src/components/charts/chart-card.tsx`

**Props:** `spec: ChartAssemblyInput`, `imageBase64?: string`, `svg?: string`, `title?: string`, `onDownload?: () => void`

Renders within a bordered `Card`:
- **Header:** chart type label + "Flint" badge, format toggle (SVG/PNG), Download button
- **Body:** Conditionally renders:
  - SVG via `dangerouslySetInnerHTML` with `class="vis-flint-chart"`
  - Base64 PNG `<img>` element
  - Placeholder "Chart rendering..." while streaming

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

- **Login:** POST to `/auth/login`, stores `genbi_token` + `genbi_user` in `localStorage` (via `lib/auth-storage.ts`)
- **Session restoration:** On mount, reads from `localStorage`. If parsing fails, clears both.
- **Loading guard:** While `loading` is true, renders nothing (or bouncing dots in `AuthGuard`).

### `AuthGuard` Component

Wraps protected pages. Shows:
- Loading: bouncing dots animation
- Unauthenticated: `router.replace("/login")` redirect
- Authenticated: children

### `LoginForm` Component

**File:** `src/components/auth/login-form.tsx` — extracted, reusable email/password form with `onSuccess` callback. Used by the `/login` page, which navigates to `/chat` after a successful sign-in.

---

## UI Components (shadcn/ui)

**File:** `src/components/ui/*.tsx` | **Utility:** `cn()` from `@/lib/shadcn`

All 11 components use Radix UI primitives and Tailwind CSS with class-variance-authority (CVA) for variants.

| Component | Primitive | Variants / Notes |
|---|---|---|
| `Avatar` | `@radix-ui/react-avatar` | Root (40x40, rounded-full), Image, Fallback (gray bg, centered initials) |
| `Badge` | Plain div | `default` (brand), `secondary`, `destructive`, `outline`, `success`, `warning`. Pill shape, text-xs |
| `Button` | `@radix-ui/react-slot` (asChild) | `default` (brand+shadow), `destructive`, `outline`, `secondary`, `ghost`, `link`. Sizes: `default`, `sm`, `lg`, `icon` |
| `Card` | Plain HTML | Compound: Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter. Rounded-xl border shadow |
| `Dialog` | `@radix-ui/react-dialog` | Overlay (bg-black/50), Content (centered, rounded-xl), with X close button |
| `DropdownMenu` | `@radix-ui/react-dropdown-menu` | Content (z-50, min-w-8rem), Items with keyboard shortcuts, Separator |
| `Input` | Plain `<input>` | h-10, rounded-lg border, focus ring-brand-600 |
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
  data: { values?: Record<string, unknown>[]; url?: string };
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

Minimal hero (logo, tagline, CTA). The CTA routes to `/login` when signed out and `/chat` when signed in.

### `login/page.tsx` — Login Page

Redirects to `/chat` if already authenticated; otherwise renders `LoginForm`, which navigates to `/chat` on success.

### `chat/page.tsx` — Chat Page

Wraps `ChatView` in `AuthGuard` (redirects to `/login` when signed out). The header's database icon navigates to `/explore`.

### `explore/page.tsx` — Explore Page (Phase 10)

Wraps `ExploreView` (`components/explore/explore-view.tsx`) in `AuthGuard`. The semantic-layer workbench:

- **Catalog**: metrics from `GET /metrics/list` as clickable cards (title, cube, `metric_type` badge); selecting one sets the query's measure.
- **Query builder**: native `<select>` elements (no new deps) for measure, group-by dimension (from the measure's dimensions), optional time granularity (day/month via its first time dimension), and row limit.
- **Run**: `POST /metrics/query` → results table (hand-built Tailwind `<table>`, cube-prefix-stripped keys) +, when sliced by a dimension, a bar chart: the client builds a `ChartAssemblyInput` from the result rows, renders via `POST /charts/render`, and displays through the existing `ChartCard`.
- Empty results show an RLS-aware hint (tenant has no data — `make seed`).
- API functions live in `lib/api-client.ts` (`listMetrics`, `queryMetrics`, `listDatasources`); Zod schemas (`MetricQueryRequestSchema` etc.) in `lib/validators.ts`.

### Configuration

**`next.config.js`:** `output: "standalone"` (containerized deployment)

**`tailwind.config.ts`:** Custom `brand` palette (indigo tones):
```typescript
brand: {
  50: '#edf2ff', 100: '#dbe4ff', ...,
  600: '#4c6ef5', 700: '#4263eb', ..., 900: '#1e2a8a'
}
```

---

## Build Commands

```bash
pnpm dev          # Next.js dev server (port 3000)
pnpm build        # Production build
pnpm start        # Start production server
pnpm lint         # ESLint
pnpm typecheck    # tsc --noEmit
```
