# Frontend UX Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GenBI frontend onto a working design-token system, shared UI primitives, a decomposed chat experience, and a unified app shell — per the approved spec.

**Architecture:** Five phases executed as six mergeable units: P0 foundation (tokens, dead code, docs) → P1 shared primitives → P2a chat decomposition (behavior parity) → P2b chat UX fixes → P3 shell unification → P4 workbench migration. All work is inside `frontend/`; backend contracts are frozen.

**Tech Stack:** Next.js 15 App Router · React 19 · TypeScript strict · Tailwind CSS v4 (`@theme`) · hand-written shadcn-style primitives on Radix UI · Zod · pnpm. **No new dependencies.**

**Spec:** `docs/superpowers/specs/2026-09-22-frontend-ux-refactor-design.md` — the plan argues from the spec; read both.

## Global Constraints

- **Zero new runtime dependencies** (spec D2). Sheet is built on the installed `@radix-ui/react-dialog`. No react-query, no chart/table/toast libs.
- **Backend API contracts frozen** (spec D3). No changes to endpoints, SSE event shapes, or payloads. Backend issues are filed, not fixed.
- **Dark mode out of scope** (spec D4): no `dark:` classes; semantic tokens only make a later pass cheap.
- **Charts stay backend-rendered** SVG/PNG via existing `ChartCard` (spec D6).
- **No frontend test framework** (spec D7). Verification per task: `cd frontend && pnpm typecheck && pnpm lint` (must exit 0), `pnpm build` where noted, plus the grep/manual/live checks written into the task. Gates run from `Z:\GITHUB\GBI` (repo root) as `cd frontend && ...`.
- **Palette** (spec D8): `globals.css` hexes win; `--color-brand-200` variable name must survive (consumed by `::selection` in `globals.css:34`).
- **Import convention** (spec D9): primitives imported directly from `@/components/ui/<file>`; `@/lib/shadcn` exports only `cn()`.
- File naming kebab-case; components PascalCase; `"use client"` only where interactive (repo convention).
- No silent catches: every catch surfaces an `Alert` or a documented inline message (spec §10).
- Commit after every task (repo convention: one commit per task). Commit messages: `Frontend: <what> (UX refactor T<N>)`.

## Review Focus

The five failure modes the spec implies that typecheck/lint cannot catch, most likely first. Each is pinned to its owning task as an explicit verification step.

1. **Malformed SSE chunks** (line split across reads, `data:` prefix variants, invalid JSON): the stream parser must skip garbage without dropping valid events or killing the stream — verified in Task 14 (manual parser check) and Task 18 (live stream).
2. **Abort mid-stream** (user hits Cancel during a slow `data`/`chart` stage): spinner and streaming bubble must end; no lingering `loading` — verified in Task 16 and Task 18.
3. **Expired/invalid JWT (401)** on stream or list calls: must surface an `Alert` with the backend message, never a silent failure — verified in Task 21 (stream) and Task 5 (banner migration keeps messages visible).
4. **Empty lists** (no conversations/reports/dashboards/wiki pages/metrics/users): `EmptyState` renders with a next action, never a blank pane — verified in Task 7 and each Phase-4 view task.
5. **Long content** (long conversation titles, wide SQL, wide tables, long tenant names): truncation and `overflow-x` rules hold — verified in Task 10 (sidebar truncation), Task 11 (table scroll), Task 17 (SQL block scroll).

---

## Phase 0 — Foundation

### Task 1: `@theme` design tokens + delete dead Tailwind config

**Files:**
- Modify: `frontend/src/app/globals.css:3-12`
- Delete: `frontend/tailwind.config.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: working `bg-brand-*`/`text-brand-*`/`border-brand-*`/`ring-brand-*` utilities and semantic aliases `bg-surface`, `bg-surface-muted`, `border-border`, `text-text-muted`, `ring-ring` (used by Phase-1 primitives).

- [ ] **Step 1: Replace the `:root` palette block with `@theme`**

In `frontend/src/app/globals.css`, replace lines 3–12 (the `:root { --color-brand-* }` block) with:

```css
@theme {
  /* Brand scale (globals.css hexes win; 300/400 filled from old config) */
  --color-brand-50: #eef2ff;
  --color-brand-100: #e0e7ff;
  --color-brand-200: #c7d2fe;   /* keep name: ::selection consumes it */
  --color-brand-300: #91a7ff;
  --color-brand-400: #748ffc;
  --color-brand-500: #6366f1;
  --color-brand-600: #4c6ef5;
  --color-brand-700: #4263eb;
  --color-brand-800: #364fc7;
  --color-brand-900: #2b3a9e;

  /* Semantic aliases (dark-ready; used by new/refactored components) */
  --color-surface: #ffffff;
  --color-surface-muted: #f9fafb;   /* gray-50 */
  --color-border: #e5e7eb;          /* gray-200 */
  --color-border-strong: #d1d5db;   /* gray-300 */
  --color-text-muted: #6b7280;      /* gray-500 */
  --color-ring: var(--color-brand-600);
}
```

Delete `frontend/tailwind.config.ts` (`git rm frontend/tailwind.config.ts`). Nothing imports it; no `@config` directive exists.

- [ ] **Step 2: Build and prove the utilities are emitted**

Run: `cd frontend && pnpm build`
Then: `grep -rl "bg-brand-600" .next/static/css` (from `frontend/`)
Expected: build succeeds; grep finds at least one CSS file containing `.bg-brand-600`. **This is the Phase-0 acceptance test (spec §1 criterion 1).** Also `grep -c "tailwind.config" src/app/globals.css` → 0.

- [ ] **Step 3: Typecheck + lint**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/globals.css frontend/tailwind.config.ts
git commit -m "Frontend: emit brand tokens via Tailwind v4 @theme; drop dead config (UX refactor T1)"
```

### Task 2: Tokenize landing + login dark surfaces

**Files:**
- Modify: `frontend/src/app/page.tsx:87-89,93,97,165,203`
- Modify: `frontend/src/components/auth/login-form.tsx:49-52,55,58-61`

**Interfaces:**
- Consumes: Task 1 tokens (brand utilities now emit).
- Produces: no inline hex styles remain in `src/` (verifiable by grep).

- [ ] **Step 1: Replace inline styles with utilities**

In `app/page.tsx`: delete the white-on-white comment block (`:87-89`); replace `style={{backgroundColor:"#0f172a"}}` (`:93`,`:165`) by adding `bg-slate-900` to those elements' className; `rgba(15,23,42,0.8)` (`:97`) → `bg-slate-900/80`; `#020617` (`:203`) → `bg-slate-950`. (Tailwind's `slate-900` IS `#0f172a` and `slate-950` IS `#020617`, so visuals are identical.)

In `components/auth/login-form.tsx`: delete the "not vanish on a white panel" comment (`:49-52`); `:55` `#0f172a` → `bg-slate-900`; `:58-61` inline radial-gradient → Tailwind arbitrary value on the same element: `bg-[radial-gradient(circle_at_70%_20%,rgba(76,110,245,0.45),transparent_60%),radial-gradient(circle_at_20%_80%,rgba(67,211,151,0.25),transparent_60%)]` (adjust stops to match the current gradient read from the file; keep identical colors).

- [ ] **Step 2: Grep-verify no inline hex remains**

Run: `cd frontend && grep -rn "style={{" src/ | grep -i "#[0-9a-f]\{3,6\}\|rgba(" || echo CLEAN`
Expected: `CLEAN`.

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors. Then:

```bash
git add frontend/src/app/page.tsx frontend/src/components/auth/login-form.tsx
git commit -m "Frontend: tokenize landing/login dark surfaces, drop inline-style fallbacks (UX refactor T2)"
```

### Task 3: Dead-code purge + `ChartAssemblyInput` unification

**Files:**
- Modify: `frontend/src/lib/api-client.ts` (delete `sendChat` :107-109, `ChatResponse` :92-105, `listDatasources` :242-246 + `DatasourceSummary` :235-241, `healthCheck` :821-823)
- Modify: `frontend/src/lib/validators.ts` (delete `ChatResponseSchema` :13, `MetricSummarySchema` :57, `MetricQueryRequestSchema` :78, `ChartAssemblyInputSchema` :119, `MetricDefinitionSchema` :143, and now-dangling inferred types)
- Modify: `frontend/src/components/charts/chart-card.tsx` (delete `ChartGrid` :89+, `onDownload` prop :17,57, local `ChartAssemblyInput` :5; import from `@/types/chart`)
- Modify: `frontend/src/components/chat/chat-view.tsx:14`, `frontend/src/components/reports/reports-view.tsx:18`, `frontend/src/components/dashboards/dashboards-view.tsx:19`, `frontend/src/components/explore/explore-view.tsx:11` (import type from `@/types/chart`, not from chart-card)
- Modify: `frontend/src/lib/shadcn.ts` (drop primitive re-exports, keep `cn`)
- Delete: `frontend/src/types/index.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: single `ChartAssemblyInput` type at `@/types/chart`; `validators.ts` exports exactly: `ChatRequestSchema`, `SSEEventSchema` (+ `SSEEvent` type), `TenantProvisionSchema`, `LLMConfigSchema`, `LoginRequestSchema`, `LoginResponseSchema`, `MetricListResponseSchema`, `MetricQueryResponseSchema` (+ inferred types). **Kept schemas get consumers in later tasks; deleting them is a plan failure.**

- [ ] **Step 1: Verify zero importers before each deletion**

Run: `cd frontend && grep -rn "sendChat\|listDatasources\|healthCheck\|ChatResponseSchema\|MetricSummarySchema\|MetricQueryRequestSchema\|ChartAssemblyInputSchema\|MetricDefinitionSchema\|ChartGrid\|onDownload\|@/types/index\|from \"@/types\"" src/ --include=*.tsx --include=*.ts | grep -v "lib/api-client.ts\|lib/validators.ts\|charts/chart-card.tsx\|types/"`
Expected: no output (any hit = stop, reassess — the study found none).

- [ ] **Step 2: Delete + unify the chart type**

Apply the deletions listed under Files. In `chart-card.tsx`: replace the local interface with `import type { ChartAssemblyInput } from "@/types/chart";`, delete the `onDownload` prop from the props interface and the Download button branch that calls it (`:57`), delete the `ChartGrid` export at file end. In the four views, change the type import: `import type { ChartAssemblyInput } from "@/types/chart";` (keep `import { ChartCard } from "@/components/charts/chart-card";`). `types/chart.ts` keeps `data: { values?: ...; url?: ... }` (superset — ChartCard already conditionally renders).

- [ ] **Step 3: Reduce `lib/shadcn.ts` to `cn()`**

First: `cd frontend && grep -rn "from \"@/lib/shadcn\"" src/ | grep -v "cn" || echo ONLY_CN`
Expected: `ONLY_CN` (then rewrite the file to export only `cn`; otherwise fix the importers shown).

- [ ] **Step 4: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors (a missing-export type error here means a deletion hit a live importer — restore and reassess).

```bash
git add frontend/src
git commit -m "Frontend: purge dead API helpers/schemas/components; unify ChartAssemblyInput (UX refactor T3)"
```

### Task 4: Rewrite `docs/frontend-guide.md` to current reality

**Files:**
- Modify: `docs/frontend-guide.md` (full rewrite)

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: docs naming the `@theme` tokens, the purge, and the current route tree.

- [ ] **Step 1: Rewrite the guide**

Replace the file with a current-state guide: tech stack table (add Tailwind v4 `@theme` tokens with the brand scale; remove `tailwind.config.ts` mentions); project tree including `dashboards/`, `wiki/`, `settings/`, `admin/`, `(app)` route group + `AppShell`/`PageHeader`; API client section without the deleted functions (`sendChat`, `listDatasources`, `healthCheck`); pages section for all 15 routes (`/`, `/login`, `/chat`, `/explore`, `/reports`, `/dashboards`, `/wiki`, `/settings`, `/admin`, `/admin/tenants`, `/admin/tenants/[id]`, `/admin/admins`, `/admin/audit`); note the guide is further updated as Phases 1–4 land.

- [ ] **Step 2: Commit**

```bash
git add docs/frontend-guide.md
git commit -m "Docs: rewrite frontend guide to current tree and @theme tokens (UX refactor T4)"
```

---

## Phase 1 — Shared primitives

### Task 5: `Alert` primitive + migrate every banner

**Files:**
- Create: `frontend/src/components/ui/alert.tsx`
- Modify (banner call sites): `frontend/src/components/wiki/wiki-view.tsx:245` · `frontend/src/components/settings/settings-view.tsx:71` · `frontend/src/components/reports/reports-view.tsx:182` · `frontend/src/components/explore/explore-view.tsx:131` · `frontend/src/components/dashboards/dashboards-view.tsx:202` · `frontend/src/app/admin/tenants/[id]/page.tsx:121,126` · `frontend/src/app/admin/tenants/page.tsx:92` · `frontend/src/app/admin/page.tsx:49` · `frontend/src/app/admin/admins/page.tsx:79,83` · `frontend/src/app/admin/audit/page.tsx:63` · `frontend/src/components/auth/login-form.tsx:131` · inline red `<p>`s: `frontend/src/components/settings/users-admin.tsx:104,232`, `frontend/src/components/settings/llm-provider.tsx:116,255`, `frontend/src/components/admin/tenant-llm-panel.tsx:112,271`, `frontend/src/app/admin/tenants/[id]/page.tsx:225`

**Interfaces:**
- Consumes: Task 1 tokens; `cn` from `@/lib/shadcn`; `class-variance-authority` (installed).
- Produces: `<Alert variant title? onDismiss? action?>` used everywhere later tasks render errors/notices.

- [ ] **Step 1: Create the primitive**

```tsx
import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, CheckCircle2, X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

const alertVariants = cva("flex items-start gap-2 rounded-lg border px-4 py-2 text-sm", {
  variants: {
    variant: {
      error: "bg-red-50 border-red-200 text-red-700",
      success: "bg-green-50 border-green-200 text-green-700",
      warning: "bg-amber-50 border-amber-200 text-amber-800",
    },
  },
  defaultVariants: { variant: "error" },
});

const ICONS = { error: AlertCircle, success: CheckCircle2, warning: AlertTriangle } as const;

export interface AlertProps extends VariantProps<typeof alertVariants> {
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
  action?: ReactNode;
  className?: string;
}

export function Alert({ variant = "error", title, children, onDismiss, action, className }: AlertProps) {
  const Icon = ICONS[variant ?? "error"];
  return (
    <div className={cn(alertVariants({ variant }), className)} role="alert">
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        <div className="break-words">{children}</div>
      </div>
      {action}
      {onDismiss && (
        <button onClick={onDismiss} className="shrink-0 rounded p-0.5 hover:bg-black/5" title="Dismiss">
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Migrate every call site**

Replace each `bg-red-50 border-red-200 …` banner div with `<Alert variant="error">{message}</Alert>`; the two green notices (`admins/page.tsx:83`, `tenants/[id]/page.tsx:126`) with `<Alert variant="success">`; the six inline `<p className="text-xs text-red-600">` with `<Alert variant="error" className="text-xs">` (or keep as field-level `<p>` only where it sits directly under its input inside a form grid — convert to Alert otherwise). Chat warnings (amber boxes in `chat-view.tsx`) are migrated in Task 17, not here.

- [ ] **Step 3: Gates + grep + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && grep -rn "bg-red-50\|bg-green-50" src/ || echo CLEAN`
Expected: 0 errors; `CLEAN` (amber warning boxes in chat remain until Task 17 — that is expected, do not touch them here).

```bash
git add frontend/src
git commit -m "Frontend: Alert primitive; migrate all error/success banners (UX refactor T5)"
```

### Task 6: `Loader` primitive + migrate dot loaders

**Files:**
- Create: `frontend/src/components/ui/loader.tsx`
- Modify: `frontend/src/components/dashboards/dashboards-view.tsx:209` · `frontend/src/components/explore/explore-view.tsx:138` · `frontend/src/components/reports/reports-view.tsx:223` · `frontend/src/components/settings/settings-view.tsx:113` · `frontend/src/app/login/page.tsx:22` · `frontend/src/app/admin/page.tsx:56` · `frontend/src/app/admin/audit/page.tsx:85` · `frontend/src/app/admin/tenants/page.tsx:131` · `frontend/src/app/admin/tenants/[id]/page.tsx:82`

**Interfaces:**
- Consumes: Task 1 tokens.
- Produces: `<Loader size? fullScreen? label? />`; guards migrate in Task 28, not here.

- [ ] **Step 1: Create the primitive**

```tsx
import { cn } from "@/lib/shadcn";

const DOT = { sm: "w-2 h-2", md: "w-3 h-3", lg: "w-4 h-4" } as const;

export function Loader({
  size = "md",
  fullScreen = false,
  label,
  className,
}: {
  size?: keyof typeof DOT;
  fullScreen?: boolean;
  label?: string;
  className?: string;
}) {
  const dots = (
    <div className="flex items-center justify-center space-x-2" role="status" aria-label={label ?? "Loading"}>
      {[0, 75, 150].map((delay) => (
        <div
          key={delay}
          className={cn(DOT[size], "bg-brand-600 rounded-full animate-bounce")}
          style={delay ? { animationDelay: `${delay}ms` } : undefined}
        />
      ))}
      {label && <span className="ml-2 text-sm text-text-muted">{label}</span>}
    </div>
  );
  if (fullScreen) {
    return <div className={cn("flex items-center justify-center h-screen", className)}>{dots}</div>;
  }
  return <div className={cn("flex items-center justify-center py-16", className)}>{dots}</div>;
}
```

Note: current dots use `delay-75`/`delay-150` classes; inline `animationDelay` is equivalent and keeps one code path.

- [ ] **Step 2: Migrate the 9 call sites** listed under Files to `<Loader />` (or `<Loader fullScreen />` where the old markup used `h-screen`/`min-h-screen`). Do not touch `auth-provider.tsx` (Task 28).

- [ ] **Step 3: Gates + grep + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && grep -rn "animate-bounce" src/ | grep -v "ui/loader.tsx\|auth/auth-provider.tsx" || echo CLEAN`
Expected: 0 errors; `CLEAN`.

```bash
git add frontend/src
git commit -m "Frontend: Loader primitive; migrate view dot-loaders (UX refactor T6)"
```

### Task 7: `EmptyState` primitive + adopt in five views

**Files:**
- Create: `frontend/src/components/ui/empty-state.tsx`
- Modify: `frontend/src/components/explore/explore-view.tsx:269-274` · `frontend/src/components/dashboards/dashboards-view.tsx:300-304` · `frontend/src/components/wiki/wiki-view.tsx:220-223` · `frontend/src/components/admin/tenant-llm-panel.tsx:156-158` · `frontend/src/app/admin/tenants/[id]/page.tsx:243-245`

**Interfaces:**
- Consumes: Task 1 tokens.
- Produces: `<EmptyState icon? title description? action? variant? />`; chat's rich empty state migrates in Task 17.

- [ ] **Step 1: Create the primitive**

```tsx
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = "centered",
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  variant?: "card" | "inline" | "centered";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 text-center",
        variant === "card" && "rounded-xl border border-gray-200 bg-white px-6 py-12",
        variant === "inline" && "py-6",
        variant === "centered" && "py-16",
        className,
      )}
    >
      {Icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-600">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <p className="text-sm font-medium text-gray-900">{title}</p>
      {description && <div className="max-w-sm text-sm text-text-muted">{description}</div>}
      {action}
    </div>
  );
}
```

- [ ] **Step 2: Adopt at the five sites** — explore's bordered box → `variant="card"` (keep the RLS/`make seed` hint text verbatim); dashboards/wiki/admin sites → `variant="inline"` or `"centered"` matching current padding; keep role-conditional suffixes (wiki) as the `description` node.

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src
git commit -m "Frontend: EmptyState primitive; adopt in five views (UX refactor T7)"
```

### Task 8: `Sheet` primitive (Radix-Dialog side panel)

**Files:**
- Create: `frontend/src/components/ui/sheet.tsx`

**Interfaces:**
- Consumes: `@radix-ui/react-dialog` (installed; no new dep per Global Constraints), `cn`.
- Produces: `<Sheet open onOpenChange side? title?>`, `<SheetContent>`, used by Tasks 22/26 (mobile list panels) — signature below is the contract those tasks code against.

- [ ] **Step 1: Create the primitive**

```tsx
"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

/**
 * Sheet — a side-anchored panel built on the installed Radix Dialog
 * (focus trap, Escape to close, aria wiring) so no new dependency is
 * introduced. Hosts in-view sidebar lists below their breakpoint.
 */
export function Sheet({
  open,
  onOpenChange,
  side = "left",
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: "left" | "right";
  title?: string;
  children: ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-900/60" />
        <DialogPrimitive.Content
          className={cn(
            "fixed inset-y-0 z-50 flex w-72 flex-col bg-white shadow-xl outline-none",
            side === "left" ? "left-0 border-r border-gray-200" : "right-0 border-l border-gray-200",
          )}
        >
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 px-4">
            <DialogPrimitive.Title className="text-sm font-semibold text-gray-900">
              {title ?? "Panel"}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close className="rounded-lg p-2 text-gray-500 hover:bg-gray-100">
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
```

- [ ] **Step 2: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/ui/sheet.tsx
git commit -m "Frontend: Sheet primitive on Radix Dialog (UX refactor T8)"
```

### Task 9: `ConfirmDialog` primitive + replace the five hand-rolled modals

**Files:**
- Create: `frontend/src/components/ui/confirm-dialog.tsx`
- Modify: `frontend/src/components/settings/users-admin.tsx:204,247,283` (create user, reset password, delete confirm)
- Modify: `frontend/src/app/admin/tenants/page.tsx:178` (provision tenant)
- Modify: `frontend/src/app/admin/tenants/[id]/page.tsx:251` (decommission tenant, typed-slug confirm)

**Interfaces:**
- Consumes: existing `frontend/src/components/ui/dialog.tsx` (`Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter` — verify exact exports in that file and match), `Button`, `Input`, `Alert`.
- Produces: `<ConfirmDialog open onOpenChange title description? confirmLabel? requireText? onConfirm busy?>`; **zero `fixed inset-0` overlays remain in `src/`.**

- [ ] **Step 1: Create the primitive**

```tsx
"use client";

import { useState, type ReactNode } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  confirmVariant = "destructive",
  requireText,
  requireTextLabel,
  onConfirm,
  busy = false,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  /** "destructive" for delete/danger, "default" for form submits. */
  confirmVariant?: "default" | "destructive";
  /** When set, the confirm button stays disabled until the input matches. */
  requireText?: string;
  requireTextLabel?: string;
  onConfirm: () => void;
  busy?: boolean;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  const blocked = requireText !== undefined && typed !== requireText;
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setTyped(""); onOpenChange(o); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}
        {requireText !== undefined && (
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={requireTextLabel ?? `Type ${requireText} to confirm`}
            autoFocus
          />
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} disabled={blocked || busy}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Replace the five hand-rolled overlays**

Each `fixed inset-0 z-50 flex items-center justify-center bg-black/30` block becomes a `ConfirmDialog` (form-body content moves into `children`; the decommission dialog passes `requireText={tenant.slug}` preserving today's typed confirmation). One shape for everything: destructive confirmations (delete user, decommission tenant) keep `confirmVariant="destructive"`; non-destructive form modals (create user, reset password, provision tenant) use the same `ConfirmDialog` with `confirmVariant="default"`. Keep every existing error `Alert` inside the dialogs.

- [ ] **Step 3: Gates + grep + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && grep -rn "fixed inset-0" src/ --include=*.tsx | grep -v "ui/sheet.tsx\|ui/dialog.tsx\|layout/app-shell.tsx" || echo CLEAN`
Expected: 0 errors; `CLEAN` (app-shell's mobile drawer is migrated in Task 23/24 phase work, leave it).

```bash
git add frontend/src
git commit -m "Frontend: ConfirmDialog; replace hand-rolled modal overlays (UX refactor T9)"
```

### Task 10: `SidebarList` primitive

**Files:**
- Create: `frontend/src/components/ui/sidebar-list.tsx`

**Interfaces:**
- Consumes: Task 1 tokens, `cn`, `Button`, lucide `Plus`.
- Produces: the exact component below; consumers in Tasks 17/22 (chat), 26/30 (reports), 26/31 (dashboards). Wiki's recursive `TreeView` is NOT folded into this component — it reuses only the header/label/plus shell (Task 32).

- [ ] **Step 1: Create the primitive**

```tsx
"use client";

import { Plus } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

export interface SidebarListItem {
  id: string;
  label: string;
  secondary?: ReactNode;
}

/**
 * SidebarList — the shared "label + '+' + selectable rows" block used by
 * chat conversations, reports, and dashboards sidebars. Presentational;
 * views wrap it in an <aside> on desktop and in <Sheet> on mobile.
 */
export function SidebarList({
  title,
  items,
  activeKey,
  onSelect,
  onCreate,
  createTitle,
  emptyText,
}: {
  title: string;
  items: SidebarListItem[];
  activeKey?: string | null;
  onSelect?: (id: string) => void;
  onCreate?: () => void;
  createTitle?: string;
  emptyText?: string;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</p>
        {onCreate && (
          <button
            onClick={onCreate}
            title={createTitle ?? `New ${title.toLowerCase()}`}
            className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-900"
          >
            <Plus className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {items.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-text-muted">{emptyText ?? "Nothing here yet"}</p>
        ) : (
          <ul className="space-y-0.5">
            {items.map((item) => {
              const active = item.id === activeKey;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => onSelect?.(item.id)}
                    className={cn(
                      "w-full rounded-lg border-l-2 px-3 py-2 text-left transition-colors",
                      active
                        ? "border-brand-600 bg-brand-50 text-gray-900"
                        : "border-transparent text-gray-700 hover:bg-gray-100",
                    )}
                  >
                    <span className="block truncate text-sm">{item.label}</span>
                    {item.secondary && (
                      <span className="mt-0.5 block truncate text-xs text-text-muted">{item.secondary}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors. (Adoption happens in Tasks 17/26/30/31; the component is the deliverable here.)

```bash
git add frontend/src/components/ui/sidebar-list.tsx
git commit -m "Frontend: SidebarList primitive (UX refactor T10)"
```

### Task 11: `DataTable` primitive + proving adoption on `/admin/admins`

**Files:**
- Create: `frontend/src/components/ui/data-table.tsx`
- Modify: `frontend/src/app/admin/admins/page.tsx:110` (superadmin table)

**Interfaces:**
- Consumes: Task 6 `Loader`, Task 1 tokens.
- Produces: `<DataTable columns rows keyField emptyText loading? />` — the contract Phase-4 tasks (29/30/33/34) code against.

- [ ] **Step 1: Create the primitive**

```tsx
"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";
import { Loader } from "@/components/ui/loader";

export interface Column<T> {
  key: string;
  header: ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
  render?: (row: T) => ReactNode;
}

export function DataTable<T extends object>({
  columns,
  rows,
  keyField,
  emptyText = "No rows.",
  loading = false,
}: {
  columns: Column<T>[];
  rows: T[];
  keyField: keyof T | ((row: T) => string);
  emptyText?: string;
  loading?: boolean;
}) {
  const keyOf = (row: T, i: number) =>
    typeof keyField === "function"
      ? keyField(row)
      : String((row as Record<string, unknown>)[keyField as string] ?? i);
  if (loading) return <Loader />;
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left">
            {columns.map((c) => (
              <th
                key={c.key}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500",
                  c.align === "right" && "text-right",
                  c.align === "center" && "text-center",
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-text-muted">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={keyOf(row, i)} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "px-4 py-2.5 align-top",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.className,
                    )}
                  >
                    {c.render ? c.render(row) : ((row as Record<string, unknown>)[c.key] as ReactNode)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Migrate `/admin/admins` table** to `DataTable` (5 columns: user/email, granted_by, granted_at, revoked status, actions — keep the existing revoke/grant buttons via `render`), preserving its empty-row text.

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src
git commit -m "Frontend: DataTable primitive; adopt on /admin/admins (UX refactor T11)"
```

### Task 12: Shared `LLMProviderForm` (BYOK) — one form, two modes

**Files:**
- Create: `frontend/src/components/llm/llm-provider-form.tsx`
- Modify: `frontend/src/components/settings/llm-provider.tsx` (becomes thin self-mode wrapper)
- Modify: `frontend/src/components/admin/tenant-llm-panel.tsx` (becomes thin tenant-mode wrapper + keeps its spend table)

**Interfaces:**
- Consumes: api-client `getLLMConfig`, `saveLLMConfig`, `validateLLMConfig`, `setLLMStatus`, `deleteLLMConfig` (self) and `getTenantLLM`, `putTenantLLM`, `patchTenantLLMStatus` (tenant); `LLMConfigSchema` from `@/lib/validators`; `Alert` (T5), `Loader` (T6), `Button`, `Input`.
- Produces: `<LLMProviderForm mode="self" />` and `<LLMProviderForm mode="tenant" tenantId={id} />`. **Spend-attribution table stays in `tenant-llm-panel.tsx`, outside the shared form.**

- [ ] **Step 1: Extract the shared form**

Move the duplicated state (`provider`, `apiKey`, `baseUrl`, `reasoningModel`, `fastModel`, `embeddingModel`), defaults (identical in both files), and `formBody()` logic into `llm-provider-form.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteLLMConfig,
  getLLMConfig,
  getTenantLLM,
  patchTenantLLMStatus,
  putTenantLLM,
  saveLLMConfig,
  setLLMStatus,
  validateLLMConfig,
  type LLMConfigInput,
  type LLMProviderConfig,
} from "@/lib/api-client";
import { LLMConfigSchema } from "@/lib/validators";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader } from "@/components/ui/loader";

export function LLMProviderForm({
  mode,
  tenantId,
}: {
  mode: "self" | "tenant";
  tenantId?: string;
}) {
  // adapter: every backend call branches on mode, exactly like the two
  // current implementations — self has Validate + Revert-to-platform;
  // tenant submits with confirmLabel "Force-set" and has no revert.
  // …state identical to current llm-provider.tsx (provider/apiKey/baseUrl/
  // reasoningModel/fastModel/embeddingModel, loading, saving, error, notice,
  // current config, validation result)…
}
```

Full field grid, status toggle, validate ping, and masked `key_last4` display copy verbatim from the current `settings/llm-provider.tsx` (the richer of the two); the mode adapter maps: load = `mode === "self" ? getLLMConfig() : getTenantLLM(tenantId!)`; save = `saveLLMConfig(body)` / `putTenantLLM(tenantId!, body)`; status = `setLLMStatus(s)` / `patchTenantLLMStatus(tenantId!, s)`; validate and delete render only in self mode. Submit label: `mode === "self" ? "Save" : "Force-set"`. Zod-validate the body with `LLMConfigSchema` before submit (both modes — today both rely on the schema indirectly; make it explicit).

- [ ] **Step 2: Rewire the two wrappers** — `settings/llm-provider.tsx` renders `<LLMProviderForm mode="self" />` plus its security note; `admin/tenant-llm-panel.tsx` renders `<LLMProviderForm mode="tenant" tenantId={tenantId} />` above its existing spend table (`getTenantLLM(tenantId, days)` usage data — keep the panel's own fetch for the spend rows if the shared form doesn't expose them).

- [ ] **Step 3: Gates + manual check + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors. Manual (live stack, later phase gate): settings BYOK save/validate/disable; admin tenant LLM force-set — both show masked `key_last4`.

```bash
git add frontend/src
git commit -m "Frontend: shared LLMProviderForm for settings + admin BYOK (UX refactor T12)"
```

### Task 13: AppShell user card → `DropdownMenu` + `Avatar` + `Separator` + `Tooltip`

**Files:**
- Modify: `frontend/src/components/layout/app-shell.tsx:86-120` (UserCard), `:149-190` (mobile drawer/top-bar icon buttons)

**Interfaces:**
- Consumes: existing primitives `dropdown-menu.tsx`, `avatar.tsx`, `separator.tsx`, `tooltip.tsx` (installed, currently unused), `useAuth`.
- Produces: all five orphan primitives wired (spec §6); no visual regression in the dark sidebar.

- [ ] **Step 1: Rewire `UserCard`**

Replace the initials `div` (`:100-102`) with `<Avatar><AvatarFallback className="bg-brand-600 text-sm font-semibold text-white">{initials || "U"}</AvatarFallback></Avatar>`; replace the bare logout icon button with a `DropdownMenu`: trigger = the row's ellipsis/chevron icon button (`MoreVertical` from lucide), content holds `Settings` (Link to `/settings`), `Separator`, `Sign out` (calls `logout()`). Dark-sidebar styling: `DropdownMenuContent className="bg-slate-800 border-white/10 text-slate-200"` so the menu reads on the dark rail (verify against the primitive's default classes and override via `className` only — never edit the ui primitive, repo rule).

- [ ] **Step 2: `Tooltip` on icon-only buttons**

Wrap the shell's remaining icon-only buttons in `Tooltip` with their existing `title` text as content: the mobile top-bar menu button (`:181-187`, "Open navigation") and the mobile-drawer close button (`:164-169`). Use the primitive's `Tooltip`/`TooltipTrigger`/`TooltipContent` exports (check `ui/tooltip.tsx` for whether a `TooltipProvider` wrapper is required and add it at the AppShell root if so).

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors; build compiles all routes (Phase-1 exit gate).

```bash
git add frontend/src/components/layout/app-shell.tsx
git commit -m "Frontend: AppShell user card on DropdownMenu/Avatar/Separator (UX refactor T13)"
```

---

## Phase 2a — Chat decomposition (behavior parity)

### Task 14: Harden `streamChat` + move login into api-client

**Files:**
- Modify: `frontend/src/lib/api-client.ts:119-166` (streamChat), add `login` near the top (after `sendFeedback`)
- Modify: `frontend/src/components/auth/auth-provider.tsx:60-86`

**Interfaces:**
- Consumes: `SSEEventSchema`/`SSEEvent`, `LoginResponseSchema` from `@/lib/validators`; existing `ApiError`, `CHAT_STREAM_URL`, `getStoredToken`.
- Produces:
  - `streamChat(req: ChatRequest, onEvent: (event: SSEEvent) => void, onError: (error: ApiError) => void, onClose?: () => void): AbortController` — **typed event param (was `Record<string, unknown>`)**; throws-shaped errors via `onError`; `onClose` fires when the body ends without a `done` event (defensive finalization).
  - `login(email: string, password: string): Promise<LoginResponse>` where `LoginResponse = { access_token: string; token_type: string; user: { id: string; email: string; name: string; tenant_id: string; roles: string[]; platform_admin?: boolean } }`.

- [ ] **Step 1: Replace `streamChat`**

```typescript
export function streamChat(
  req: ChatRequest,
  onEvent: (event: SSEEvent) => void,
  onError: (error: ApiError) => void,
  onClose?: () => void,
): AbortController {
  const controller = new AbortController();
  const token = getStoredToken();

  (async () => {
    try {
      const res = await fetch(CHAT_STREAM_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({ message: res.statusText }));
        throw new ApiError(res.status, error.code ?? "UNKNOWN", error.message ?? "Request failed");
      }
      const reader = res.body?.getReader();
      if (!reader) throw new ApiError(0, "NO_STREAM", "No response stream");

      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const raw of lines) {
          const line = raw.trim();
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(line.indexOf(":") + 1).trim();
          if (!payload) continue;
          try {
            onEvent(SSEEventSchema.parse(JSON.parse(payload)));
          } catch {
            // Skip unparseable/invalid chunks — never kill the stream (Review Focus 1)
          }
        }
      }
      if (!controller.signal.aborted) onClose?.();
    } catch (err) {
      if (controller.signal.aborted) return;
      onError(err instanceof ApiError ? err : new ApiError(0, "NETWORK", err instanceof Error ? err.message : "Network error"));
    }
  })();

  return controller;
}
```

Add `import { LoginResponseSchema, SSEEventSchema } from "@/lib/validators";` and `import type { SSEEvent } from "@/lib/validators";` (match the file's existing type-import style). Add:

```typescript
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    name: string;
    tenant_id: string;
    roles: string[];
    platform_admin?: boolean;
  };
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await request<unknown>("/auth/login", { method: "POST", body: { email, password } });
  return LoginResponseSchema.parse(data);
}
```

- [ ] **Step 2: Rewire `auth-provider.tsx` login**

Replace the raw `fetch` block (`:63-78`) with:

```typescript
import { login as apiLogin } from "@/lib/api-client";
// inside useCallback:
const data = await apiLogin(email, password);
setToken(data.access_token);
setUser(data.user);
storeSession(data.access_token, data.user);
```

`ApiError` propagates to `LoginForm`, which already renders `err.message` — the backend's typed message now survives (previously `err.message` could be undefined → "Login failed"). Verify the `User` interface in auth-provider stays structurally identical to `LoginResponse["user"]`.

- [ ] **Step 3: Parser verification (Review Focus 1)**

Manual check (no test framework): read the new parser and confirm — (a) a `data:` payload split across two reads stays in `buffer` until `\n` arrives; (b) `data:{...}` (no space) and `data:  {...}` (extra space) both parse; (c) invalid JSON and schema-invalid events are skipped without throwing; (d) non-`data:` lines (comments/heartbeats) are skipped. Then gates.

- [ ] **Step 4: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors (chat-view still uses its inline SSE — removed in Task 18; no other streamChat consumers exist yet).

```bash
git add frontend/src/lib/api-client.ts frontend/src/components/auth/auth-provider.tsx
git commit -m "Frontend: harden streamChat (res.ok, trim, schema-validated, typed) + api-client login (UX refactor T14)"
```

### Task 15: `useConversations` hook + shared chat types

**Files:**
- Create: `frontend/src/components/chat/chat-types.ts`
- Create: `frontend/src/hooks/use-conversations.ts`

**Interfaces:**
- Consumes: api-client `listConversations`, `ConversationSummary`.
- Produces:
  - `chat-types.ts`: `StreamStage { stage: string; data: SSEEvent }`, `ChatMessage { id: string; role: "user" | "assistant"; content: string; streaming: boolean; stages: StreamStage[]; sql?: string; chartSpec?: Record<string, unknown>; chartSvg?: string; chartBase64?: string; narrative?: string; warnings: string[]; sessionId?: string; feedback?: 1 | -1 | 0; needsConfirm?: boolean; rowEstimate?: number | null; confirmQuery?: string; streamError?: string }` (verbatim from `chat-view.tsx:23-49` plus `streamError?: string` used by Task 21), and `newMessageId(): string` (the `uuid()` helper from `chat-view.tsx:54-61`, renamed and exported).
  - `useConversations()` returning `{ conversations, conversationId, listError, refresh, selectConversation, startNewChat, handleServerAssignedId }`.

- [ ] **Step 1: Create `chat-types.ts`** — move the two interfaces verbatim from `chat-view.tsx:23-49`, add `streamError?: string` to `ChatMessage`, move+rename `uuid()` → `newMessageId()`.

- [ ] **Step 2: Create `use-conversations.ts`**

```typescript
"use client";

import { useCallback, useEffect, useState } from "react";
import { listConversations, type ConversationSummary } from "@/lib/api-client";

/** Conversation list + active id (Phase 14). Message state lives in use-chat-stream. */
export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await listConversations();
      setConversations(res.conversations);
      setListError(null);
    } catch {
      setListError("Conversations couldn't be loaded.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectConversation = useCallback((id: string) => setConversationId(id), []);
  const startNewChat = useCallback(() => setConversationId(null), []);
  const handleServerAssignedId = useCallback((id: string) => setConversationId(id), []);

  return {
    conversations,
    conversationId,
    listError,
    refresh,
    selectConversation,
    startNewChat,
    handleServerAssignedId,
  };
}
```

Note: this removes the current silent catch (`chat-view.tsx:83-85`) — `listError` surfaces in the sidebar via `Alert` in Task 17's `ConversationSidebar` (Global Constraint: no silent catches).

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/chat/chat-types.ts frontend/src/hooks/use-conversations.ts
git commit -m "Frontend: chat types module + useConversations hook (UX refactor T15)"
```

### Task 16: `useChatStream` hook (parity extraction)

**Files:**
- Create: `frontend/src/hooks/use-chat-stream.ts`

**Interfaces:**
- Consumes: T14 `streamChat`; T15 `ChatMessage`/`newMessageId`; api-client `listConversationMessages`, `sendFeedback`; `ChatRequestSchema`.
- Produces: `useChatStream({ conversationId, onConversationId, onTurnComplete })` returning `{ messages, loading, send, cancel, loadHistory, reset, setFeedback }`. **PARITY: identical semantics to current `chat-view.tsx` — including the confirm-via-`send(override, true)` path and always-send-score feedback; Tasks 19/20 flip those on purpose.**

- [ ] **Step 1: Create the hook** — move, verbatim in behavior, from `chat-view.tsx`: `updateMessageStage` (`:127-162`), `handleSend` → `send` (`:164-273`, minus the inline fetch — it now calls T14's `streamChat`), `handleCancel` → `cancel` (`:275-290`), `handleFeedback` → `setFeedback` (`:294-306`), history mapping from `handleSelectConversation` (`:96-109`) → `loadHistory(id)`, plus `reset()` (clears messages) and a `messagesRef` mirror:

```typescript
"use client";

import { useCallback, useRef, useState } from "react";
import {
  listConversationMessages,
  sendFeedback,
  streamChat,
} from "@/lib/api-client";
import { ChatRequestSchema } from "@/lib/validators";
import type { SSEEvent } from "@/lib/validators";
import { newMessageId, type ChatMessage } from "@/components/chat/chat-types";

export function useChatStream({
  conversationId,
  onConversationId,
  onTurnComplete,
}: {
  conversationId: string | null;
  onConversationId: (id: string) => void;
  onTurnComplete: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const streamingMsgRef = useRef<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const finalize = useCallback(() => {
    setLoading(false);
    abortRef.current = null;
    streamingMsgRef.current = null;
  }, []);

  // updateMessageStage: copy the body verbatim from chat-view.tsx:127-162
  // (stage accumulation incl. done/confirmation_required handling).

  const startStream = useCallback(
    (query: string, assistantId: string, confirmLarge: boolean) => {
      setLoading(true);
      abortRef.current = streamChat(
        {
          query,
          confirm_large_query: confirmLarge || undefined,
          conversation_id: conversationId ?? undefined,
        },
        (event: SSEEvent) => {
          updateMessageStage(assistantId, event.event, event);
          if (event.event === "start" && event.conversation_id) onConversationId(event.conversation_id);
          if (event.event === "done") {
            onTurnComplete();
            finalize();
          }
        },
        () => {
          // Parity for Task 16 (Task 21 replaces this with streamError):
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: "Sorry, something went wrong.", streaming: false }
                : m,
            ),
          );
          finalize();
        },
        () => finalize(), // onClose without done: never leave the spinner running (Review Focus 2)
      );
      streamingMsgRef.current = assistantId;
    },
    [conversationId, onConversationId, onTurnComplete, updateMessageStage, finalize],
  );

  // send(overrideQuery?, confirmLarge = false): parity with handleSend —
  // validate via ChatRequestSchema (silent reject preserved until Task 21),
  // append user+assistant pair, then startStream(query, msgId, confirmLarge).

  // cancel(): parity with handleCancel (abort + end in-flight bubble).

  // loadHistory(id): parity with the mapping at chat-view.tsx:96-109
  // (id: `${id}-${i}`, role, content, sql, narrative; stages/warnings empty).

  // setFeedback(msgId, score): parity with handleFeedback (toggle locally,
  // always POST the pressed score, swallow errors) — Task 20 fixes semantics.

  // reset(): setMessages([]).

  return { messages, loading, send, cancel, loadHistory, reset, setFeedback };
}
```

(The commented blocks are verbatim moves from the cited lines of `chat-view.tsx`, which Task 18 then deletes — implement both tasks from the same pre-refactor file in one working session or rebase carefully.)

- [ ] **Step 2: Abort-mid-stream check (Review Focus 2)**

Read-through verification: Cancel during a slow stage → `abort()` → streamChat's loop exits via signal; `onError` early-returns on aborted; `cancel()`'s local finalize ends the bubble ("Cancelled.") and spinner. No path leaves `loading === true`.

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/hooks/use-chat-stream.ts
git commit -m "Frontend: useChatStream hook on hardened streamChat (parity) (UX refactor T16)"
```

### Task 17: Chat presentational components

**Files:**
- Create: `frontend/src/components/chat/stage-badges.tsx`, `sql-block.tsx`, `feedback-thumbs.tsx`, `large-query-confirm.tsx`, `chat-input.tsx`, `message-list.tsx`, `assistant-message-card.tsx`, `conversation-sidebar.tsx`

**Interfaces:**
- Consumes: T15 `ChatMessage`; T5 `Alert` (warnings → `variant="warning"`); T7 `EmptyState`; T10 `SidebarList`; existing `Card`, `Badge`, `Button`, `Input`, `Skeleton`, `MarkdownText`, `ChartCard`.
- Produces (exact props — Task 18 wires these, do not drift):
  - `<StageBadges stages={StreamStage[]} />` — `stageLabels` hoisted to module scope (currently recreated per render at `chat-view.tsx:309-317`).
  - `<SqlBlock sql={string} />` — dark terminal block + copy button (from `chat-view.tsx` SQL section, ~`:433-470`).
  - `<FeedbackThumbs feedback={1|-1|0|undefined} disabled? onFeedback={(score: 1|-1) => void} />` (from `:478-508`).
  - `<LargeQueryConfirm rowEstimate={number|null} loading? onConfirm={() => void} />` (from `:511-529`; body text preserved).
  - `<ChatInput value onChange onSend onCancel loading error? />` — input bar from `:541-581`; `error?: string | null` renders a hint line under the input (used by Task 21; pass nothing for now).
  - `<AssistantMessageCard message={ChatMessage} loading onFeedback onConfirm />` — the assistant `Card` from `:405-532`, composing StageBadges, streaming `Skeleton` (`:430-432`), SqlBlock, `ChartCard`, `MarkdownText` narrative, warnings `Alert variant="warning"` (replacing the amber boxes — this is their migration point from Task 5), FeedbackThumbs, LargeQueryConfirm.
  - `<MessageList messages loading onSuggestion onFeedback onConfirm />` — scroll container + auto-scroll (`chatEndRef` + effect from `:122-125`) + empty state (`:360-389` → `<EmptyState icon={BarChart3} variant="centered">` keeping the exact greeting text and the three suggestion chips, which call `onSuggestion(text)`) + user bubbles (`:398-402`) and assistant cards.
  - `<ConversationSidebar conversations activeId listError onSelect onNewChat />` — `SidebarList` (`items = conversations.map(c => ({ id: c.id, label: c.title }))`), `onCreate = onNewChat`, plus `listError` rendered as `<Alert variant="error" className="m-2 text-xs">` when set (replaces today's silent catch); keep the exact sidebar width/border shell from `:321-353` for the desktop host.

- [ ] **Step 1: Extract each component** — cut the JSX from the cited `chat-view.tsx` ranges into the files above; keep classNames identical except where `Alert`/`EmptyState`/`SidebarList` replace bespoke blocks.

- [ ] **Step 2: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/chat
git commit -m "Frontend: extract chat presentational components (UX refactor T17)"
```

### Task 18: Recompose `ChatView` as thin composer (parity gate)

**Files:**
- Modify: `frontend/src/components/chat/chat-view.tsx` (585 → ~100 lines)

**Interfaces:**
- Consumes: T15/T16 hooks, T17 components.
- Produces: `ChatView` with zero stream parsing, zero stage logic; deleted: `CHAT_STREAM_URL` import, `updateMessageStage`, `stageLabels`, `uuid`, the interfaces (now in chat-types).

- [ ] **Step 1: Rewrite `chat-view.tsx`**

```tsx
"use client";

import { useCallback, useState } from "react";
import { useConversations } from "@/hooks/use-conversations";
import { useChatStream } from "@/hooks/use-chat-stream";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";

export function ChatView() {
  const convos = useConversations();
  const stream = useChatStream({
    conversationId: convos.conversationId,
    onConversationId: convos.handleServerAssignedId,
    onTurnComplete: convos.refresh,
  });
  const [input, setInput] = useState("");

  const handleSelect = useCallback(
    (id: string) => {
      if (stream.loading) return;
      convos.selectConversation(id);
      stream.loadHistory(id);
    },
    [convos, stream],
  );

  const handleNewChat = useCallback(() => {
    if (stream.loading) return;
    convos.startNewChat();
    stream.reset();
    setInput("");
  }, [convos, stream]);

  const handleSend = useCallback(() => {
    stream.send(input);
    setInput("");
  }, [input, stream]);

  return (
    <div className="flex h-full bg-gray-50">
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <ConversationSidebar
          conversations={convos.conversations}
          activeId={convos.conversationId}
          listError={convos.listError}
          onSelect={handleSelect}
          onNewChat={handleNewChat}
        />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <MessageList
          messages={stream.messages}
          loading={stream.loading}
          onSuggestion={(text) => stream.send(text)}
          onFeedback={stream.setFeedback}
          onConfirm={(query) => stream.send(query, true)}
        />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onCancel={stream.cancel}
          loading={stream.loading}
        />
      </div>
    </div>
  );
}
```

(`onConfirm` still routes through `send(query, true)` — parity; Task 19 swaps it to `stream.confirmLargeQuery()`.)

- [ ] **Step 2: Parity gate**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors, all routes compile. Live-stack smoke (if Docker is up, else defer to Phase-2b gate): login → send query → stage badges progress → SQL/chart/narrative render → sidebar lists the conversation → select an old conversation (history replays) → new chat.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/chat-view.tsx
git commit -m "Frontend: ChatView as thin composer over hooks + components (UX refactor T18)"
```

---

## Phase 2b — Chat UX fixes

### Task 19: Large-query confirm reuses the pending turn

**Files:**
- Modify: `frontend/src/hooks/use-chat-stream.ts` (add `confirmLargeQuery`, drop the `send(override, confirm)` path)
- Modify: `frontend/src/components/chat/chat-view.tsx` (`onConfirm` → `stream.confirmLargeQuery`)

**Interfaces:**
- Consumes: T16/T18.
- Produces: `useChatStream` return gains `confirmLargeQuery: () => void`; `send(text: string)` is single-purpose (the `overrideQuery`/`confirmLarge` params are deleted).

- [ ] **Step 1: Implement `confirmLargeQuery`**

```typescript
const confirmLargeQuery = useCallback(() => {
  const pending = [...messagesRef.current].reverse().find((m) => m.role === "assistant" && m.needsConfirm);
  const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
  if (!pending || !lastUser || loading) return;
  setMessages((prev) =>
    prev.map((m) =>
      m.id === pending.id
        ? { ...m, streaming: true, needsConfirm: false, content: "", stages: [], warnings: [], streamError: undefined }
        : m,
    ),
  );
  startStream(lastUser.content, pending.id, true);
}, [loading, startStream]);
```

Remove `send`'s `overrideQuery`/`confirmLarge` parameters and the now-dead branch; ChatView's `onConfirm` becomes `stream.confirmLargeQuery` (no arg — update `LargeQueryConfirm`'s call site via MessageList's `onConfirm` prop type: `() => void`).

- [ ] **Step 2: Verify** — read-through: confirm click → ONE assistant bubble resets and re-streams with `confirm_large_query: true`; no new user bubble; `needsConfirm` panel disappears. Then `cd frontend && pnpm typecheck && pnpm lint`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src
git commit -m "Frontend: confirm large query reuses pending turn — no duplicate bubble (UX refactor T19)"
```

### Task 20: Feedback sends `0` on clear, optimistic with rollback

**Files:**
- Modify: `frontend/src/hooks/use-chat-stream.ts` (`setFeedback`)

**Interfaces:**
- Consumes: T16.
- Produces: `setFeedback(msgId: string, score: 1 | -1): void` — toggles; POSTs the RESULTING score (`1 | -1 | 0`); rolls back on `ApiError`.

- [ ] **Step 1: Replace `setFeedback`**

```typescript
const setFeedback = useCallback((msgId: string, score: 1 | -1) => {
  const msg = messagesRef.current.find((m) => m.id === msgId);
  if (!msg?.sessionId) return;
  const next: 1 | -1 | 0 = msg.feedback === score ? 0 : score;
  setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: next } : m)));
  sendFeedback(msg.sessionId, next).catch(() => {
    setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: msg.feedback ?? 0 } : m)));
  });
}, []);
```

Fixes three bugs at once: clear never reached the server; the stale-closure read (`chat-view.tsx:299`); silent failure now rolls the thumb back so UI and server stay consistent.

- [ ] **Step 2: Gates + live note**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors. Live verification (Phase-2b exit): thumbs-up then clear → `SELECT feedback_score FROM audit_log …` shows `0`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-chat-stream.ts
git commit -m "Frontend: feedback clear sends score 0; optimistic toggle with rollback (UX refactor T20)"
```

### Task 21: Input validation hint + stream-error Alert with retry

**Files:**
- Modify: `frontend/src/hooks/use-chat-stream.ts` (add `inputError`, `streamError` on message, `retry(msgId)`)
- Modify: `frontend/src/components/chat/chat-input.tsx` (hint line)
- Modify: `frontend/src/components/chat/assistant-message-card.tsx` (error Alert + retry button)
- Modify: `frontend/src/components/chat/message-list.tsx`, `chat-view.tsx` (prop threading)

**Interfaces:**
- Consumes: T16–T18.
- Produces: hook returns gain `inputError: string | null`, `retry(msgId: string): void`; `ChatInput` gets `error?: string | null`; `AssistantMessageCard` gets `onRetry: (msgId: string) => void`.

- [ ] **Step 1: Hook changes** — `send` sets `setInputError(issue.message)` on `ChatRequestSchema` failure (instead of silent return) and clears it on success; expose `inputError`. In `startStream`'s `onError`, set `{ ...m, streaming: false, streamError: error.message }` (replaces the "Sorry, something went wrong." content write). Add:

```typescript
const retry = useCallback(
  (msgId: string) => {
    const failed = messagesRef.current.find((m) => m.id === msgId);
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!failed || !lastUser || loading) return;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId ? { ...m, streaming: true, streamError: undefined, content: "", stages: [], warnings: [] } : m,
      ),
    );
    startStream(lastUser.content, msgId, false);
  },
  [loading, startStream],
);
```

- [ ] **Step 2: UI** — `ChatInput`: under the input, `{error && <p className="mt-1 text-xs text-red-600">{error}</p>}` (whitespace-only and >2000-char queries now explain themselves — Review Focus: silent rejection removed). `AssistantMessageCard`: when `message.streamError`, render `<Alert variant="error" action={<Button size="sm" variant="outline" onClick={() => onRetry(message.id)}>Retry</Button>}>{message.streamError}</Alert>` in place of the content area. Thread `onRetry` through MessageList from ChatView (`stream.retry`).

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src
git commit -m "Frontend: chat input hints + stream-error alert with retry (UX refactor T21)"
```

### Task 22: Chat conversation list on mobile (`Sheet`)

**Files:**
- Modify: `frontend/src/components/chat/chat-view.tsx`

**Interfaces:**
- Consumes: T8 `Sheet`, T17 `ConversationSidebar`, lucide `MessageSquare`.
- Produces: conversations reachable below `md` (spec §1 criterion 2 for chat).

- [ ] **Step 1: Wire the Sheet** — in ChatView: `const [listOpen, setListOpen] = useState(false);` render a toggle button as the first row of the content column, `className="flex md:hidden items-center gap-2 border-b border-gray-200 bg-white px-4 py-2 text-sm text-gray-700"` with the `MessageSquare` icon and "Conversations"; `<Sheet open={listOpen} onOpenChange={setListOpen} title="Conversations"><ConversationSidebar …same props… /></Sheet>`; `handleSelect`/`handleNewChat` also call `setListOpen(false)`.

- [ ] **Step 2: Gates + mobile check + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors (Phase-2 exit gate). Manual: narrow viewport → toggle opens sheet → select conversation → sheet closes, history loads.

```bash
git add frontend/src/components/chat/chat-view.tsx
git commit -m "Frontend: conversations reachable on mobile via Sheet (UX refactor T22)"
```

---

## Phase 3 — Shell unification

### Task 23: Merge the admin portal into the AppShell

**Files:**
- Move: `frontend/src/app/admin/*` → `frontend/src/app/(app)/admin/*` (`git mv "frontend/src/app/admin" "frontend/src/app/(app)/admin"`)
- Replace: `frontend/src/app/(app)/admin/layout.tsx` (guard-only)
- Modify: `frontend/src/components/layout/app-shell.tsx:31-84` (Platform nav section)
- Create: `frontend/src/components/layout/page-container.tsx`
- Modify: the five admin pages (`page.tsx`, `tenants/page.tsx`, `tenants/[id]/page.tsx`, `admins/page.tsx`, `audit/page.tsx`) — adopt `PageHeader` + `PageContainer`

**Interfaces:**
- Consumes: existing `PlatformAdminGuard` (`auth-provider.tsx:154`), `PageHeader`, lucide icons.
- Produces: `<PageContainer>` (`h-full overflow-y-auto` + `max-w-5xl` column) reused by all admin pages; AppShell `ADMIN_NAV`; URLs unchanged (`/admin`, `/admin/tenants`, `/admin/tenants/[id]`, `/admin/admins`, `/admin/audit`).

- [ ] **Step 1: Move + guard-only layout**

```bash
git mv "frontend/src/app/admin" "frontend/src/app/(app)/admin"
```

Replace `(app)/admin/layout.tsx` with:

```tsx
"use client";

import type { ReactNode } from "react";
import { PlatformAdminGuard } from "@/components/auth/auth-provider";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <PlatformAdminGuard>{children}</PlatformAdminGuard>;
}
```

(The old light sidebar, its nav, and its `max-w-5xl mx-auto px-6 py-8` main wrapper are deleted. AuthGuard comes from `(app)/layout.tsx`; PlatformAdminGuard here. All imports use the `@/` alias, so the move breaks none.)

- [ ] **Step 2: AppShell Platform section**

In `app-shell.tsx`: add

```tsx
const ADMIN_NAV = [
  { href: "/admin", label: "Overview", icon: Gauge },
  { href: "/admin/tenants", label: "Tenants", icon: Building2 },
  { href: "/admin/admins", label: "Superusers", icon: ShieldCheck },
  { href: "/admin/audit", label: "Audit log", icon: ScrollText },
];
```

(import `Gauge`, `Building2`, `ShieldCheck`, `ScrollText` from lucide). In `SidebarNav`, after the Account section, render a third "Platform" section when `user?.platform_admin`, mapping `ADMIN_NAV` with the same `item()` renderer — except active state for `/admin` must be exact (`pathname === "/admin"`), others `startsWith`; adjust `isActive` to `href === "/admin" ? pathname === href : pathname === href || pathname.startsWith(\`${href}/\`)`. Remove the old single "Admin portal" link from the Account section (`:79-80`).

- [ ] **Step 3: `PageContainer` + admin page headers**

```tsx
import type { ReactNode } from "react";

export function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-8">{children}</div>
    </div>
  );
}
```

Each admin page: wrap content in `<PageContainer>` and add a `PageHeader` (icon + title + description + existing primary action, e.g. Tenants' "Provision tenant" button moves into `actions`). Delete the deleted layout's "Back to GenBI" link concept — AppShell already cross-links.

- [ ] **Step 4: Gates + live check + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors; build output still lists `/admin`, `/admin/tenants`, `/admin/tenants/[id]`, `/admin/admins`, `/admin/audit` (route-group move changes no URLs). Live: superuser sees Platform section; normal demo user does not; non-superuser hitting `/admin` sees the guard message.

```bash
git add frontend/src
git commit -m "Frontend: admin portal inside AppShell with Platform nav section (UX refactor T23)"
```

### Task 24: Remove `<main key={pathname}>` remount

**Files:**
- Modify: `frontend/src/components/layout/app-shell.tsx:122-198`

**Interfaces:**
- Consumes: nothing new.
- Produces: navigation no longer remounts page subtrees; scroll resets explicitly.

- [ ] **Step 1: Replace keyed main with scroll restoration**

```tsx
const mainRef = useRef<HTMLElement>(null);
useEffect(() => {
  mainRef.current?.scrollTo(0, 0);
}, [pathname]);
// …
<main ref={mainRef} className="min-h-0 flex-1">
  {children}
</main>
```

(add `useRef`/`useEffect` to the imports).

- [ ] **Step 2: Remount-dependency sweep**

Read each of the seven workspace views' top-level effects and confirm initialization depends on mounts of *data*, not on the route remount: chat (loads conversations on mount — fine), explore (metrics on mount — fine), reports/dashboards/wiki/settings/admin pages (lists on mount — fine). Expected finding: none rely on remount; if one does (e.g. a view that only fetches when first mounted and goes stale when revisited), add a pathname-keyed refetch in that view — record what was found in the commit message.

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/layout/app-shell.tsx
git commit -m "Frontend: drop keyed-main remount; explicit scroll restoration (UX refactor T24)"
```

### Task 25: Route-level boundaries (`not-found` / `error` / `loading`)

**Files:**
- Create: `frontend/src/app/not-found.tsx`
- Create: `frontend/src/app/error.tsx`
- Create: `frontend/src/app/(app)/loading.tsx`
- Create: `frontend/src/app/(app)/error.tsx`

**Interfaces:**
- Consumes: T5 `Alert`, T6 `Loader`, `Button`, Next `Link`.
- Produces: branded 404, root error boundary, in-shell loading + error boundaries.

- [ ] **Step 1: Create the four files**

`app/not-found.tsx` (server component, no hooks):

```tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-gray-50 text-center">
      <p className="text-4xl font-semibold text-gray-900">404</p>
      <p className="text-sm text-text-muted">This page doesn&apos;t exist.</p>
      <Button asChild><Link href="/">Back to GenBI</Link></Button>
    </div>
  );
}
```

`app/error.tsx` and `app/(app)/error.tsx` (`"use client"`; receive `{ error, reset }`): centered `Alert variant="error" title="Something went wrong"` showing `error.message`, with a `Button` "Try again" (`onClick={reset}`) and a `Link` home; the `(app)` variant renders inside the content column (`h-full` centering), the root one `min-h-screen`.

`app/(app)/loading.tsx`:

```tsx
import { Loader } from "@/components/ui/loader";

export default function Loading() {
  return <Loader className="h-full" />;
}
```

- [ ] **Step 2: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors; `/not-found` appears in build output.

```bash
git add frontend/src/app
git commit -m "Frontend: route-level not-found/error/loading boundaries (UX refactor T25)"
```

### Task 26: Mobile sheets for reports / dashboards / wiki lists

**Files:**
- Modify: `frontend/src/components/reports/reports-view.tsx` (sidebar `:133-160`, PageHeader `:164`)
- Modify: `frontend/src/components/dashboards/dashboards-view.tsx` (sidebar `:139-173`, PageHeader `:177`)
- Modify: `frontend/src/components/wiki/wiki-view.tsx` (sidebar `:186-232`, PageHeader `:236`)

**Interfaces:**
- Consumes: T8 `Sheet`, lucide `List` (or `PanelLeft`), existing PageHeader `actions` slot.
- Produces: the three lists reachable below `md`. (If Tasks 30/31/32 land first, wrap the `SidebarList` output instead of the legacy JSX — same props, same Sheet.)

- [ ] **Step 1: Per view** — `const [listOpen, setListOpen] = useState(false);` add a `md:hidden` icon button (`List`) to the view's `PageHeader` `actions`; render `<Sheet open={listOpen} onOpenChange={setListOpen} title="Reports|Dashboards|Pages">` hosting the same sidebar block; selecting an item (or creating) closes the sheet. Wiki's sheet includes its search input and the editor-only new-page button (guard condition unchanged).

- [ ] **Step 2: Gates + grep + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors. Manual per view at mobile width: list opens, selection works, sheet closes.

```bash
git add frontend/src
git commit -m "Frontend: reports/dashboards/wiki lists reachable on mobile via Sheet (UX refactor T26)"
```

### Task 27: Deep-linkable selection via `useSelectionParam`

**Files:**
- Create: `frontend/src/hooks/use-selection-param.ts`
- Modify: `frontend/src/components/chat/chat-view.tsx` (`conv`), `frontend/src/components/reports/reports-view.tsx` (`report`), `frontend/src/components/dashboards/dashboards-view.tsx` (`dash`), `frontend/src/components/wiki/wiki-view.tsx` (`page`)
- Modify: the four page files (`frontend/src/app/(app)/{chat,reports,dashboards,wiki}/page.tsx`) — add `export const dynamic = "force-dynamic"` (client views reading `useSearchParams`; they are auth-gated and have no static value)

**Interfaces:**
- Consumes: `next/navigation` `useSearchParams`/`usePathname`/`useRouter`.
- Produces: `useSelectionParam(param: string): [string | null, (id: string | null) => void]`; refresh/share restores the selected conversation/report/dashboard/wiki page (spec §8 item 5).

- [ ] **Step 1: Create the hook**

```typescript
"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** Two-way bind a selection id to a URL search param (deep links + refresh). */
export function useSelectionParam(param: string): [string | null, (id: string | null) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const value = searchParams.get(param);
  const set = useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id) params.set(param, id);
      else params.delete(param);
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname);
    },
    [pathname, router, searchParams],
  );
  return [value, set];
}
```

- [ ] **Step 2: Wire each view** — two effects with loop guards, e.g. chat: `const [selected, setSelected] = useSelectionParam("conv");` — (a) when `selected !== convos.conversationId` and `selected` is set and differs, call `handleSelect(selected)`; (b) when `convos.conversationId` changes (click or server-assigned on `start`), `setSelected(convos.conversationId)`; new chat → `setSelected(null)`. Guard both effects against redundant sets (`if (selected === convos.conversationId) return;`). Reports/dashboards/wiki: same shape — param value drives the initial/active item; invalid ids fall back to the current default view (no crash, Review Focus 4).

- [ ] **Step 3: Gates + manual + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors (force-dynamic prevents the `useSearchParams` Suspense build error). Manual: select report → reload → same report open; copy URL to new tab → same selection.

```bash
git add frontend/src
git commit -m "Frontend: deep-linkable sidebar selection via search params (UX refactor T27)"
```

### Task 28: Guards onto `Loader`

**Files:**
- Modify: `frontend/src/components/auth/auth-provider.tsx:129-138,164-169`

**Interfaces:**
- Consumes: T6 `Loader`.
- Produces: both guards render `<Loader fullScreen />`; zero `animate-bounce` outside `loader.tsx` (spec §1 criterion 2, loader half).

- [ ] **Step 1: Swap both loading branches** — AuthGuard and PlatformAdminGuard `if (loading)` returns become `return <Loader fullScreen />;` (import from `@/components/ui/loader`).

- [ ] **Step 2: Gates + grep + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build && grep -rn "animate-bounce" src/ | grep -v "ui/loader.tsx" || echo CLEAN`
Expected: 0 errors; build green; `CLEAN`. (Phase-3 exit gate.)

```bash
git add frontend/src/components/auth/auth-provider.tsx
git commit -m "Frontend: auth guards on shared Loader (UX refactor T28)"
```

---

## Phase 4 — Workbench migration

### Task 29: Explore onto shared primitives + schema-validated metric APIs

**Files:**
- Modify: `frontend/src/lib/api-client.ts:207,231` (`listMetrics`, `queryMetrics` — parse responses with `MetricListResponseSchema` / `MetricQueryResponseSchema`)
- Modify: `frontend/src/components/explore/explore-view.tsx` (results table `:243` → `DataTable`)

**Interfaces:**
- Consumes: T11 `DataTable`, kept validators schemas, existing Alert/Loader/EmptyState adoptions.
- Produces: `listMetrics`/`queryMetrics` return schema-parsed data (invalid payloads throw `ApiError`-surfaced ZodError — wrap: `catch` in the view shows the existing error Alert).

- [ ] **Step 1: Schema-validate the two endpoints**

```typescript
export async function listMetrics(): Promise<MetricListResponse> {
  return MetricListResponseSchema.parse(await request<unknown>("/metrics/list"));
}
export async function queryMetrics(req: MetricQueryRequest): Promise<MetricQueryResponse> {
  return MetricQueryResponseSchema.parse(await request<unknown>("/metrics/query", { method: "POST", body: req }));
}
```

(import the schemas; keep the exported TS interfaces as the parse targets — align them if the schema inference differs.)

- [ ] **Step 2: Results table → `DataTable`** — dynamic columns built from the first row's keys (cube-prefix stripping preserved: `key.split(".").pop()`), `emptyText` keeps the RLS/`make seed` hint, `loading` prop wired to the query state. Query-builder native `<select>`s stay (Global Constraints).

- [ ] **Step 3: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src
git commit -m "Frontend: explore results on DataTable; schema-validated metric APIs (UX refactor T29)"
```

### Task 30: Reports onto `SidebarList`

**Files:**
- Modify: `frontend/src/components/reports/reports-view.tsx`

**Interfaces:**
- Consumes: T10 `SidebarList`, T5 `Alert`, T7 `EmptyState`, T26 Sheet host.
- Produces: reports sidebar renders `SidebarList` (`items = reports.map(r => ({ id: r.id, label: r.title, secondary: \`${r.section_count} sections\` }))`, `activeKey = active?.report_id`, no `onCreate` — generation lives in the main pane); warnings panel → `Alert variant="warning"`.

- [ ] **Step 1: Swap sidebar + warnings** — replace the bespoke list block with `SidebarList` inside both the desktop `<aside>` and the T26 `Sheet`; the skipped-metrics/persistence warnings block becomes `<Alert variant="warning" title="Some sections were skipped">` with the list as children; empty sidebar → `emptyText="No reports yet"`. Generate/regenerate/PDF/schedule behavior untouched.

- [ ] **Step 2: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/reports/reports-view.tsx
git commit -m "Frontend: reports on SidebarList + warning Alert (UX refactor T30)"
```

### Task 31: Dashboards onto `SidebarList` + `Dialog` create + `ConfirmDialog` actions

**Files:**
- Modify: `frontend/src/components/dashboards/dashboards-view.tsx`

**Interfaces:**
- Consumes: T9 `ConfirmDialog` (+ its `FormDialog` sibling), T10 `SidebarList`, T26 Sheet host, existing `ChartGrid`-less chart cards.
- Produces: create panel becomes a modal (`Dialog` with title input + report select + section checkboxes — same fields as today's inline panel); delete dashboard and unpin section go through `ConfirmDialog` (`variant="danger"`).

- [ ] **Step 1: Sidebar → `SidebarList`** (`items = dashboards.map(d => ({ id: d.id, label: d.title, secondary: \`${d.section_count} sections\` }))`, `onCreate` opens the create dialog) in desktop aside + Sheet.

- [ ] **Step 2: Create panel → modal** — move the inline create form into a `Dialog` opened from the sidebar `+` and the header action; same submit logic (`createDashboard` + per-section `pinSection`); validation errors via `Alert` inside the dialog.

- [ ] **Step 3: Destructive actions → `ConfirmDialog`** — delete dashboard: `requireText` unset, `confirmLabel="Delete"`; unpin section: low-severity, `confirmLabel="Unpin"`.

- [ ] **Step 4: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/dashboards/dashboards-view.tsx
git commit -m "Frontend: dashboards on SidebarList/Dialog/ConfirmDialog (UX refactor T31)"
```

### Task 32: Wiki sidebar shell alignment

**Files:**
- Modify: `frontend/src/components/wiki/wiki-view.tsx:186-232`

**Interfaces:**
- Consumes: T26 Sheet host, shared header/label styles (match `SidebarList`'s header block exactly: same padding/typography/`border-l-2` active row), existing recursive `TreeView`.
- Produces: wiki tree keeps `TreeView` but the surrounding shell (label row, editor-only `+` new-page button, search input under the header, active-node `border-l-2 border-brand-600`) is visually identical to the other three sidebars.

- [ ] **Step 1: Align the shell** — header row `px-4 py-3 border-b border-gray-200` + `text-xs font-semibold uppercase tracking-wide text-gray-500` label + `Plus` icon button (editor guard unchanged); search input directly under header; tree nodes' active state to `border-l-2 border-brand-600 bg-brand-50`. No behavior change (search, history, restore, editor untouched).

- [ ] **Step 2: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src/components/wiki/wiki-view.tsx
git commit -m "Frontend: wiki sidebar shell aligned with SidebarList pattern (UX refactor T32)"
```

### Task 33: Settings onto `Tabs` + `DataTable` + Zod forms

**Files:**
- Modify: `frontend/src/lib/validators.ts` — add `UserCreateSchema = z.object({ email: z.string().email(), password: z.string().min(8), name: z.string().min(1), roles: z.array(z.enum(["user", "admin"])).min(1) })`, `ChangePasswordSchema = z.object({ current_password: z.string().min(1), new_password: z.string().min(8) })` (align field names to the API payloads in `users-admin.tsx`/`settings-view.tsx` before writing)
- Modify: `frontend/src/components/settings/settings-view.tsx` (sections → `Tabs`; password form → `ChangePasswordSchema`)
- Modify: `frontend/src/components/settings/users-admin.tsx` (table → `DataTable`; create form → `UserCreateSchema`)
- Modify: `frontend/src/components/auth/login-form.tsx` (adopt `LoginRequestSchema` for field validation)

**Interfaces:**
- Consumes: existing `tabs.tsx` primitive, T11 `DataTable`, T12 `LLMProviderForm` (already integrated — verify only), T9 dialogs.
- Produces: settings sections as `Tabs` (Profile / Password / Users / AI Provider — Users + AI Provider tabs render only for tenant admins, same condition as today's sections); zero ad-hoc `includes("@")`/`length < 8` checks (spec §10).

- [ ] **Step 1: Sections → Tabs** — `Tabs` `defaultValue="profile"`; keep each section's content component unchanged inside `TabsContent`; conditional tabs by role exactly as the current conditional sections.

- [ ] **Step 2: Zod the three forms** — replace `users-admin.tsx:71` (`!form.email.includes("@") || form.password.length < 8`) and `settings-view.tsx:40` (`newPw.length < 8`) with schema `safeParse` + first-issue message into the existing inline error spots; login-form validates with `LoginRequestSchema` before submit.

- [ ] **Step 3: Users table → `DataTable`** — 5 columns incl. actions via `render` (role select, enable/disable, reset, delete buttons move into the actions cell; self-action disabled logic preserved).

- [ ] **Step 4: Gates + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint`
Expected: 0 errors.

```bash
git add frontend/src
git commit -m "Frontend: settings on Tabs/DataTable/Zod; login form schema-validated (UX refactor T33)"
```

### Task 34: Admin tables onto `DataTable` + final consistency sweep

**Files:**
- Modify: `frontend/src/app/(app)/admin/tenants/page.tsx:135` (tenant table)
- Modify: `frontend/src/app/(app)/admin/audit/page.tsx:89` (audit table — keep the two client-side filter inputs above it)
- Modify: `frontend/src/components/admin/tenant-llm-panel.tsx:159` (spend table)
- Modify: `frontend/src/app/(app)/admin/tenants/[id]/page.tsx` (recent-actions list — align to `DataTable` if it is a `<table>`, else leave)
- Modify: `docs/frontend-guide.md` (final state)

**Interfaces:**
- Consumes: T11 `DataTable`; everything from Phases 0–3.
- Produces: zero hand-built `<table>` outside `data-table.tsx`; spec §1 criterion 2 fully green; docs current.

- [ ] **Step 1: Migrate the tables** — columns/`render` per current markup; `emptyText` preserved per table; audit filters keep working (they filter `rows` before passing to `DataTable`).

- [ ] **Step 2: Final sweep greps** (all from `frontend/`):

```bash
grep -rn "bg-red-50\|bg-green-50" src/ || echo CLEAN_ALERTS
grep -rn "animate-bounce" src/ | grep -v "ui/loader.tsx" || echo CLEAN_LOADERS
grep -rn "fixed inset-0" src/ --include=*.tsx | grep -v "ui/sheet.tsx\|ui/dialog.tsx\|layout/app-shell.tsx" || echo CLEAN_MODALS
grep -rn "hidden md:flex" src/ --include=*.tsx | grep -v "Sheet\|sheet" || echo CHECK_SIDEBARS
grep -rn "style={{" src/ | grep -i "#[0-9a-f]\{3,6\}\|rgba(" || echo CLEAN_INLINE
grep -rn "<table" src/ --include=*.tsx | grep -v "ui/data-table.tsx\|ui/markdown.tsx" || echo CLEAN_TABLES
```

Expected: all CLEAN (CHECK_SIDEBARS may list remaining desktop `<aside>`s — each must have a Sheet counterpart in the same view; verify by reading the file, not by grep).

- [ ] **Step 3: Update `docs/frontend-guide.md`** — component inventory now includes alert/loader/empty-state/sheet/confirm-dialog/sidebar-list/data-table + `components/llm/`, `hooks/`; shell section covers the unified `(app)` group incl. admin; chat section describes hooks + components; verification section lists the gates.

- [ ] **Step 4: Full gates + build + commit**

Run: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`
Expected: 0 errors; all routes compile (Phase-4/refactor exit gate). Live-stack pass per spec §11 (demo stack on :3003): the full browser checklist.

```bash
git add frontend/src docs/frontend-guide.md
git commit -m "Frontend: admin tables on DataTable; final UX-refactor sweep + docs (UX refactor T34)"
```

---

## Live verification (whole-refactor exit gate, spec §11)

After Task 34, on the demo stack (`make demo-up && make demo-seed`, frontend on :3003):

1. Login (demo admin) → brand-colored primary buttons/active nav (token acceptance in the browser).
2. Chat: query streams stages → cancel mid-stream (spinner ends) → large-query confirm reuses one bubble → thumbs up then clear (server gets 0) → empty/invalid input hint → stream error alert + retry → mobile-width conversation sheet.
3. Shell: `/admin/*` inside AppShell for superuser, hidden for normal user; refresh on `/reports?report=<id>` restores selection; 404 page on a bad URL; no remount flicker between workspace pages.
4. Workbenches: explore query → DataTable + chart; reports generate + warnings alert; dashboards create/pin/unpin/delete dialogs; wiki tree/search/edit; settings tabs + users CRUD + BYOK save/validate; admin tenant provision + force-set LLM.
5. `make verify` stays green (backend untouched).
