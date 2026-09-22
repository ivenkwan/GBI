# Frontend UX Refactor — Design Spec

> **Date:** 2026-09-22 · **Status:** awaiting review · **Scope:** `frontend/` only — no backend API changes
> **Approved direction (user, 2026-09-22):** sequenced hybrid — thin foundation slice → chat flagship → shell unification → workbench migration.

---

## 1. Intent & Success Criteria

GenBI's frontend grew phase-by-phase: each backend capability bolted on a page with its own copy-pasted patterns. The result is an app that feels stitched together, with a broken design-token system, unreachable mobile surfaces, silent error paths, and heavy duplication. The app shell landed 2026-09-21 (Phase 27b), but only at the top-navigation level.

**Refactor intent (confirmed with user):**

- Make the app feel like **one coherent product**, not phase artifacts.
- Fix the **trust-killers**: broken brand styling, mobile gaps, silent failures.
- The **chat flow is the flagship** and gets the deepest treatment.
- **Backend API contracts are unchanged.** This is frontend-only work.
- Primary audience: demo viewers and daily analysts on desktop; mobile must be *usable*, not necessarily polished.

**Success criteria (verifiable at the end of each phase):**

1. `bg-brand-600` and the other brand utilities are actually emitted in the built CSS (grep the `.next` build output) — today all 81 usages across 23 files are no-ops.
2. Zero hand-rolled modal overlays; zero `hidden md:flex` in-view sidebars without a mobile access path; zero copy-pasted error-banner/loader/sidebar blocks (grep counts).
3. Chat: SSE handled only by `api-client.streamChat`; no duplicate bubble on large-query confirm; feedback clear sends `score: 0`; invalid input shows feedback instead of being silently dropped.
4. Admin portal renders inside the AppShell at unchanged URLs (`/admin/*`); `<main key={pathname}>` remount removed.
5. `pnpm typecheck` 0 errors, `pnpm lint` 0 errors, `pnpm build` compiles all routes; live verification on the Docker demo stack (`make demo-up && make demo-seed`) passes the per-phase browser checklist.
6. `docs/frontend-guide.md` rewritten to match reality.

---

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **Sequenced hybrid**: Phase 0 foundation → Phase 1 primitives → Phase 2 chat → Phase 3 shell → Phase 4 workbenches. Each phase independently shippable. | User-approved 2026-09-22. Every visual decision currently lands on broken token plumbing, so the foundation is non-negotiable first. |
| D2 | **Zero new runtime dependencies.** The mobile Sheet is built on the existing `@radix-ui/react-dialog` (same technique as shadcn's sheet). No react-query, no client charting library, no toast library, no table library. | Repo convention ("no new deps" habit); demo-environment fragility history; the existing 8 Radix packages already cover every pattern we need. |
| D3 | **Backend contracts frozen.** No changes to REST endpoints, SSE event shapes, or payloads. Any bug that appears backend-side is filed, not fixed here. | Keeps blast radius frontend-only; backend has protected files and its own test gates. |
| D4 | **Dark mode: out of scope, but the token layer is built dark-ready** via semantic aliases (`surface`, `text-muted`, `border`). No `dark:` classes are added; no partial dark sweep. | YAGNI for the demo/analyst audience; agent-5 found partial dark mode would be visually broken given today's hardcoded dark shell + light views. |
| D5 | **Mobile: fix "unreachable" severity only.** Every in-view sidebar gets a drawer; grids/tables stay as-is otherwise. Desktop-first polish. | Matches the audience; bounds scope. |
| D6 | **Charts stay backend-rendered** (SVG via `dangerouslySetInnerHTML` / base64 PNG). `ChartCard` keeps its SVG/PNG toggle. | Interactive client charts are an architecture-level change (ADR territory), not a UX-refactor side quest. |
| D7 | **No frontend test framework introduced.** Verification = `typecheck`/`lint`/`build` gates + live Docker-stack browser checklists per phase. | The project has deliberately no frontend tests today; adding a framework is a separate decision. |
| D8 | **Palette: the `globals.css` hexes win.** Missing steps 300/400 are filled from `tailwind.config.ts`. | `globals.css` 500 `#6366f1` matches the landing page's `indigo-*` utilities; 600 `#4c6ef5` matches the login panel gradient `rgba(76,110,245,…)`. The config file is deleted. |
| D9 | **Import convention: direct imports from `@/components/ui/*`; `lib/shadcn.ts` keeps only `cn()`.** Its unused primitive re-exports are dropped. | Matches what feature code already does; one obvious way. |

---

## 3. Current State (evidence summary)

Full study delivered 2026-09-22 in chat; key facts with anchors:

- **Broken tokens:** `frontend/tailwind.config.ts` is never loaded (no `@config` directive); `frontend/src/app/globals.css:3-12` declares `--color-brand-*` in `:root` instead of `@theme` → no utilities generated. The two palettes disagree (e.g. brand-500 `#6366f1` vs `#5c7cfa`). `::selection` at `globals.css:34` consumes `var(--color-brand-200)` — that variable name must survive the fix.
- **Duplication:** 11 red error banners, 13 bouncing-dot loaders, 4 sidebar-list implementations, 5 hand-rolled modals vs 2 Radix dialogs, 6 hand-built tables, 1 duplicated BYOK form (`settings/llm-provider.tsx` ↔ `admin/tenant-llm-panel.tsx`). Anchors in §5–§9 below.
- **Chat:** `chat-view.tsx` (585 lines) mixes SSE parsing (199–257), a message state machine (127–162), conversation threading (76–120), feedback (292–306), and rendering (319–581). It bypasses `api-client.streamChat` (which itself swallows HTTP errors — `api-client.ts:136`). `auth-provider.tsx:63-70` logs in via raw `fetch`, bypassing api-client.
- **Shell:** admin portal has its own light layout (`app/admin/layout.tsx:16-70`) with no mobile drawer; AppShell remounts the whole page subtree per navigation (`app-shell.tsx:192`); no `loading.tsx`/`error.tsx`/`not-found.tsx` exists anywhere under `app/`; in-view sidebars are `hidden md:flex` and unreachable on mobile (`chat-view.tsx:322`, `reports-view.tsx:133`, `dashboards-view.tsx:139`, `wiki-view.tsx:186`).
- **Dead code:** see Appendix A.

---

## 4. Target Architecture

```
frontend/src/
├── app/
│   ├── layout.tsx              (unchanged: metadata + AuthProvider)
│   ├── globals.css             (@theme tokens; no :root palette)
│   ├── not-found.tsx           (NEW)
│   ├── error.tsx               (NEW)
│   ├── page.tsx                (landing — tokenized, no inline hex)
│   ├── login/page.tsx
│   └── (app)/                  (AuthGuard + AppShell; admin moves IN here)
│       ├── layout.tsx
│       ├── loading.tsx         (NEW)
│       ├── error.tsx           (NEW)
│       ├── chat|explore|reports|dashboards|wiki|settings/page.tsx
│       └── admin/              (moved from app/admin — URLs unchanged)
│           ├── layout.tsx      (PlatformAdminGuard only; no sidebar)
│           └── page.tsx, tenants/, admins/, audit/
├── components/
│   ├── ui/                     (+ alert, loader, empty-state, data-table,
│   │                            sidebar-list, sheet, confirm-dialog)
│   ├── layout/                 (app-shell, page-header — unified)
│   ├── auth/ charts/ chat/ explore/ reports/ dashboards/ wiki/ settings/ admin/
│   └── llm/llm-provider-form.tsx   (NEW — shared BYOK form)
├── hooks/
│   ├── use-chat-stream.ts      (NEW)
│   ├── use-conversations.ts    (NEW)
│   └── use-selection-param.ts  (NEW — URL search-param selection state)
└── lib/ (api-client, auth-storage, validators, shadcn/cn)
```

**Data flow (unchanged in shape, cleaned in implementation):** views → hooks → `api-client` (single SSE implementation, validated) → backend. JWT still in `localStorage`; guards stay client-side. Server-component migration is explicitly out of scope (§14).

---

## 5. Phase 0 — Foundation: tokens, dead code, docs

*Pure fixes; no visual redesign. Small, fast, unblocks everything.*

### 5.1 Token fix

- Replace the `:root` palette in `globals.css:3-12` with the `@theme` block in **Appendix B** (brand scale per D8 + semantic aliases per D4). Keep the variable name `--color-brand-200` exactly (consumed by `::selection`).
- Verify empirically: `pnpm build`, then grep the emitted CSS for `.bg-brand-600`. This is the acceptance test for the whole item.
- Delete `frontend/tailwind.config.ts` (D8; nothing references it).
- Remove inline dark fallbacks and the white-on-white comments: `app/page.tsx:87-89,93,97,165,203`; `components/auth/login-form.tsx:49-52,55,58-61`. Landing/login dark surfaces become tokenized utilities (slate scale stays, referenced via classes, not inline styles).

### 5.2 Dead-code purge

Everything in **Appendix A** marked *delete*. Notably: `api-client.sendChat`, `listDatasources`, `healthCheck`; 5 unused Zod schemas; `ChartGrid`; `ChartCard.onDownload`; `types/index.ts`; the duplicate local `ChartAssemblyInput` in `chart-card.tsx:5` (all four views switch to `@/types/chart`).

### 5.3 Docs

Rewrite `docs/frontend-guide.md` to the current tree (it describes the pre-AppShell architecture and misses dashboards/wiki/admin/settings). Updated again at each later phase where structure changes.

---

## 6. Phase 1 — Shared primitives

New files in `frontend/src/components/ui/`, kebab-case, each with CVA variants where applicable. APIs are sized to cover **all observed variants** (inventory from the duplication audit):

| Primitive | API sketch | Replaces |
|---|---|---|
| `alert.tsx` | `<Alert variant="error\|success\|warning" title? onDismiss? action?>{children}</Alert>` | 11 red banners (e.g. `explore-view.tsx:131`, `login-form.tsx:131`), 6 inline red `<p>` siblings, 2 green notices |
| `loader.tsx` | `<Loader size="sm\|md\|lg" fullScreen? label? />` — one triple-dot brand style | 13 dot call sites + divergent AuthGuard (3 dots, `auth-provider.tsx:133`) / PlatformAdminGuard (1 dot, `:167`) |
| `empty-state.tsx` | `<EmptyState icon? title description? action? variant="card\|inline\|centered" />` | 6 hand-written empty states |
| `data-table.tsx` | `<DataTable columns={[{key,header,align?,render?}]} rows keyField emptyText loading? />` | 6 hand-built tables (explore, users-admin, tenants, audit, admins, spend) |
| `sidebar-list.tsx` | `<SidebarList title onCreate? items={id,label,secondary?} activeKey emptyText onSelect renderItem? />` + mobile `Sheet` host | 4 sidebar implementations (chat `322-353`, dashboards `139-173`, reports `133-159`, wiki tree host `186-232`); admin nav instead merges into AppShell in Phase 3 |
| `sheet.tsx` | Side-panel built on the existing Radix Dialog (D2). `side="left\|right"` | No current equivalent; hosts every in-view sidebar below `md`/`lg` |
| `confirm-dialog.tsx` | `<ConfirmDialog variant="danger" requireText? onConfirm>` wrapping `Dialog` | 5 hand-rolled overlays (`users-admin.tsx:204,247,283`, `tenants/page.tsx:178`, `tenants/[id]/page.tsx:251`) |

Also in this phase:

- **`components/llm/llm-provider-form.tsx`** — one BYOK form with `mode="self" | "tenant"` (API adapter + submit label differ: "Save" vs "Force-set"); consumed by `settings/llm-provider.tsx` and `admin/tenant-llm-panel.tsx`. Identical state shape and `formBody()` logic already exist in both.
- **Wire the five orphan primitives** where they belong: `DropdownMenu` (AppShell user card), `Avatar`, `Separator`, `Tooltip` (icon-only buttons), `Tabs` (settings sections). No new deps — all already installed.
- **`lib/shadcn.ts`**: reduce to `cn()` (D9).

Migration in this phase touches call sites only where primitives are introduced; full view migrations happen in Phases 2–4.

---

## 7. Phase 2 — Chat flagship

*Two sub-steps: behavior-parity decomposition first, UX fixes second. Never both in one commit.*

### 7.1 Decomposition (behavior parity)

From `chat-view.tsx`'s current map:

- **`hooks/use-chat-stream.ts`** — owns `messages`, `loading`, `abortRef`, `streamingMsgRef`, `updateMessageStage` (127–162), send/cancel (164–290). Returns `{ messages, loading, send, cancel, confirmLargeQuery }`.
- **`hooks/use-conversations.ts`** — owns list state, active id, load/select/new (76–120) and the `start`/`done` side effects (247–252).
- **Presentational components** under `components/chat/`: `conversation-sidebar` (on `SidebarList`), `message-list` (scroll area + empty state + auto-scroll anchor), `assistant-message-card`, `stage-badges` (`stageLabels` hoisted to module scope — currently recreated per render at `309-317`), `sql-block`, `warning-banner` (on `Alert`), `feedback-thumbs`, `large-query-confirm`, `chat-input`. `ChatView` becomes a thin composer.

### 7.2 SSE unification

- Enhance `api-client.streamChat` (119–166): check `res.ok` and surface `ApiError` (currently swallowed — `api-client.ts:136`); trim lines before stripping `data: ` (`:152`); validate each event with `SSEEventSchema`. Callback signature kept (`onEvent`, `onError`) returning `AbortController`.
- Delete the inline SSE block in `chat-view.tsx:199-257`; `useChatStream` calls the enhanced `streamChat`. Conversation side effects stay in `useConversations`.
- Move login into `api-client.login()` (validating with `LoginResponseSchema`); `auth-provider.tsx:60-70` consumes it — one origin/token/error path for all network calls.

### 7.3 Correctness fixes (found by the study)

1. **Duplicate bubble on large-query confirm** (`chat-view.tsx:519-523` calls `handleSend(original, true)` which appends a new user+assistant pair): `confirmLargeQuery()` resends the *pending* turn — reset the existing assistant message and re-stream with `confirm_large_query: true`, no new user bubble.
2. **Feedback clear never reaches the server** (`:297-301`): send `score: 0` on clear; make thumbs optimistic with rollback on `ApiError`; fix the stale-closure read of `messages` (`:299`) via functional `setState`.
3. **Silent input rejection** (`:173-175`): surface a hint under the input when `ChatRequestSchema` fails (empty/whitespace/over-2000 chars).
4. **Stream errors**: render the failed assistant message with an `Alert variant="error"` + retry affordance instead of only "Sorry, something went wrong."

### 7.4 Chat UX states (per §10 standards)

Streaming bubble uses `Skeleton` (kept); stages use `StageBadges` (kept, tokenized); empty state on `EmptyState` with the three suggestion chips preserved; conversation sidebar gains a `Sheet` below `md` with a toggle in the `PageHeader` actions.

---

## 8. Phase 3 — Shell unification

1. **Admin merges into the AppShell.** Physically move `app/admin/*` → `app/(app)/admin/*` (route group ⇒ URLs unchanged). New `app/(app)/admin/layout.tsx` = `PlatformAdminGuard` only; the old light sidebar (`app/admin/layout.tsx:16-70`) is deleted. AppShell gains a conditional "Platform" nav section (visible when `user.platform_admin`) with unified active-state logic (`pathname === href || startsWith(href + "/")`, exact-match exception for `/admin`). Admin pages adopt `PageHeader` and the shared content-width wrapper; their ad-hoc `max-w-5xl mx-auto px-6 py-8` (`admin/layout.tsx:65`) moves into a shared `PageContainer`.
2. **Kill `<main key={pathname}>`** (`app-shell.tsx:192`). Replace with explicit scroll-to-top on pathname change. Sweep the seven workspace views for state that implicitly relied on remount (initialization-in-effect only, none found in audit — verify during implementation).
3. **Route boundaries:** `app/not-found.tsx`, `app/error.tsx`, `(app)/loading.tsx`, `(app)/error.tsx`. Expectation set correctly: these are error/404 boundaries and navigation fallbacks, not a perf feature (pages are client-rendered).
4. **Mobile sidebars everywhere:** chat/reports/dashboards/wiki lists move into `Sheet` below the sidebar breakpoint, toggled from each view's `PageHeader` actions. Wiki's sheet includes its search box and the admin-only new-page button (guard preserved).
5. **Deep-linkable selection:** sidebar selection state moves to URL search params via `hooks/use-selection-param.ts` — `/chat?conv=<id>`, `/reports?report=<id>`, `/dashboards?dash=<id>`, `/wiki?page=<slug>` — so refresh and shared links restore the selected item. Pure client-side; no route-file changes.
6. **Guard loaders** unify on `<Loader fullScreen />`.

---

## 9. Phase 4 — Workbench migration

Per-view migrations onto Phases 0–3 assets; no feature changes:

- **Explore:** catalog cards + query builder unchanged functionally; results → `DataTable`; errors → `Alert`; adopt `MetricListResponseSchema`/`MetricQueryResponseSchema` at the api-client boundary; RLS empty-hint → `EmptyState`.
- **Reports:** list → `SidebarList` + `Sheet`; schedule/section selects keep native `<select>` (D2); warnings panel → `Alert variant="warning"`; PDF/regenerate buttons keep behavior.
- **Dashboards:** create panel → `Dialog` (no new dep; it is inline today); grid stays `grid-cols-1 md:grid-cols-2`; unpin/delete via `ConfirmDialog`.
- **Wiki:** tree host → `SidebarList`-compatible structure; editor/history unchanged; errors → `Alert`; empty states role-aware as today.
- **Settings:** sections → `Tabs`; users table → `DataTable`; the three user modals → `Dialog`/`ConfirmDialog`; ad-hoc checks (`users-admin.tsx:71`, `settings-view.tsx:40`) → Zod schemas; BYOK → shared `LLMProviderForm` (self mode).
- **Admin:** tables → `DataTable`; provision/decommission modals → `Dialog`/`ConfirmDialog requireText`; JSON settings editor unchanged; BYOK panel → `LLMProviderForm` (tenant mode).

---

## 10. Cross-cutting standards

- **Loading:** full-page → `<Loader fullScreen />`; section → `<Loader />`; streaming content → `Skeleton`; buttons may mutate label text ("Generating…") but keep the button disabled with a spinner icon.
- **Errors:** every catch surfaces an `Alert` in-view. **No silent catches** — the "best-effort" sidebar swallow patterns are removed; failures degrade to an `Alert` with retry. Stream errors render inside the failed message.
- **Empty states:** always `EmptyState`; suggest the next action where one exists (chips in chat, create buttons elsewhere).
- **Validation:** Zod at every form and at api-client response boundaries where a schema exists. No ad-hoc `includes("@")` checks.
- **Modals:** Radix `Dialog` only; destructive actions use `ConfirmDialog` (with `requireText` for typed confirmations, as tenant decommission does today).
- **Styling:** brand/semantic tokens via `@theme`; no inline hex styles; no new color values outside `globals.css`. New/refactored components use the semantic aliases (`surface`, `text-muted`, `border`) so a future dark pass is cheap; mass-migrating existing gray classes is *not* done (YAGNI until dark mode is in scope).
- **Icons:** `lucide-react` only. **Markdown:** `MarkdownText` only.

---

## 11. Verification & Testing

No test framework added (D7). Gates per phase, in order:

1. `pnpm typecheck` → 0 errors; `pnpm lint` → 0 errors; `pnpm build` → all routes compile (route count changes logged: admin move keeps `/admin/*` URLs).
2. **Token acceptance (Phase 0 only):** grep built CSS for `.bg-brand-600`; visually confirm primary buttons/active nav render brand-colored in the browser.
3. **Live browser checklist** on the demo stack (`make demo-up && make demo-seed`, frontend on :3003):
   - Phase 2: send query → stages stream → cancel mid-stream; large-query confirm reuses one bubble; thumbs up→clear → server receives 0 (audit row `feedback_score`); invalid input hint; stream error alert; conversation switch via drawer at mobile viewport.
   - Phase 3: `/admin/*` renders in AppShell for the superuser, hidden for demo users; refresh on `/reports?report=<id>` restores selection; 404 page on bad URL; no full-page remount flicker between workspace nav.
   - Phase 4: per-view smoke of tables/dialogs/forms incl. BYOK self + tenant (force-set) flows.
4. Backend untouched ⇒ backend suite, eval gate, and `verify.sh` must remain green; run `make verify` once per phase as a smoke check.

---

## 12. Rollout & Sequencing

Six mergeable units, each green-gated: **P0** (tokens + purge + docs) → **P1** (primitives + BYOK form) → **P2a** (chat decomposition, behavior parity) → **P2b** (chat UX fixes) → **P3** (shell + boundaries + deep links) → **P4** (workbench migration, one commit per view). P0/P1 are low-risk; P2a is the risk concentration and is kept behavior-identical by construction.

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Token fix suddenly applies brand styles that were always no-ops → unintended visual shifts | Intended design all along; Phase 0 ends with a full visual sweep checklist before proceeding |
| Chat decomposition regresses streaming | P2a/P2b split; stream test matrix (cancel, confirm, error, reconnect) executed live per §11 |
| Admin move breaks routing or guards | URLs unchanged (route group); build route table compared before/after; `PlatformAdminGuard` behavior verified for both superuser and normal user |
| Removing `key={pathname}` leaks state across pages | View sweep during P3; worst case, per-view `useEffect` reset keyed on pathname |
| Scope creep into backend | D3 freeze; backend issues are filed, not fixed |

---

## 14. Out of Scope (explicit)

Dark mode (D4 — token layer is ready for it) · interactive client-side charts (D6) · server-component/streaming-render migration · react-query/SWR · i18n · breadcrumbs · a frontend test framework (D7) · onboarding tours · any backend change.

---

## Appendix A — Dead-code purge list

**Delete:** `api-client.ts` — `sendChat` (:107), `listDatasources` (:242), `healthCheck` (:821) · `validators.ts` — `ChatResponseSchema`, `MetricSummarySchema`, `MetricQueryRequestSchema`, `ChartAssemblyInputSchema`, `MetricDefinitionSchema` · `chart-card.tsx` — `ChartGrid` (:89), `onDownload` prop (:17,57) and its local `ChartAssemblyInput` (:5) · `types/index.ts` (no importers) · `tailwind.config.ts` · `shadcn.ts` primitive re-exports · inline fallbacks listed in §5.1.

**Keep & adopt (not dead):** `api-client.streamChat` (becomes the single SSE path, §7.2) · `LoginRequestSchema`, `LoginResponseSchema`, `MetricListResponseSchema`, `MetricQueryResponseSchema` (adopted at boundaries) · orphan primitives `Tabs/Tooltip/Avatar/DropdownMenu/Separator` (wired in Phase 1) · `types/chart.ts` (single home of `ChartAssemblyInput`, `ChartBackend`, `ChartOutputFormat`; the four views and api-client import it).

## Appendix B — `@theme` block (replaces `globals.css:3-12`)

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
