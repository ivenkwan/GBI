# ADR 010: OpenWiki — tenant-scoped knowledge base as live agent context

- **Status:** Proposed (2026-09-05, design phase — not yet built)
- **Context:** Per-tenant knowledge base ("openwiki") for domain knowledge,
  definitions, and business rules
- **Related:** ADR 006 (enforced RLS), ADR 009 (admin plane — wiki permissions),
  `backend/app/services/schema_retrieval.py` (retrieval pattern),
  `backend/app/agents/router_agent.py` (`chat_knowledge` intent),
  Phase 24 in `todo.md`

## Context

Each tenant accumulates knowledge the agents currently don't have: metric
definitions specific to the business ("a 'qualified pipeline' means…"),
glossaries, data caveats, fiscal-calendar rules. Today that context lives in
Slack threads and people's heads. The request is a per-tenant wiki — but an
external wiki (Notion, Confluence) would be a disconnected document dump that
users must maintain and the platform must sync.

The differentiating design: the wiki is **in the tenant's security boundary**
(same RLS recipe as everything else) and doubles as **retrieval context for the
NL2SQL pipeline** — a page written once improves every subsequent query. The
`RouterAgent` already classifies a `chat_knowledge` intent that nothing serves
today; the wiki gives it something to route to.

## Decision

### 1. Data model — pages with slugs, full revision history

```
wiki_pages
  id UUID PK, tenant_id UUID FK→tenants (indexed)
  slug VARCHAR(200)        — unique per tenant (URL + identity)
  title VARCHAR(500), content_md TEXT
  parent_slug VARCHAR(200) NULL  — lightweight hierarchy (tree in UI)
  created_by UUID, updated_by UUID, created_at, updated_at

wiki_page_revisions
  id UUID PK, page_id UUID FK→wiki_pages ON DELETE CASCADE
  version INTEGER           — monotonic per page
  title, content_md         — the snapshot
  edited_by UUID, created_at
```

Every write appends a revision first, then updates the page (single
transaction); edits are never lost, restore is `PUT` the old content forward
as a new revision (history is append-only — no in-place history rewrites).
Both tables carry the standard tenant recipe: FORCE RLS + `tenant_isolation`
on the GUC + `genbi_app` grants, via the paired `rls/*.sql` seam.

Permissions (v1, deliberately simple): **read** = any authenticated user of
the tenant; **write** = tenant `admin` role or platform superuser. The
`users.roles` array is exactly the right mechanism here (ADR 009 §1 keeps
tenant roles and platform grants separate). An `editor` role is a noted
future extension — the guard is a single role check, easy to widen.

### 2. API — CRUD plus history

```
GET    /wiki                       list (tree-ordered: parent, then title)
GET    /wiki/{slug}                current page
PUT    /wiki/{slug}                create-or-update (admin-guarded, appends revision)
DELETE /wiki/{slug}                delete page + revisions (admin-guarded)
GET    /wiki/{slug}/history        revision list (version, editor, timestamp)
POST   /wiki/{slug}/restore/{v}    restore forward as a new revision
GET    /wiki/search?q=             pgvector top-k (falls back to ILIKE on fail)
```

All reads/writes go through the GUC-writer pattern (`app/services/wiki.py`,
mirroring conversations/reports): `asyncpg` on `genbi_app`, tenant GUC per
connection, parameterized single-line statements, reads raise → 503.

### 3. Agent integration — the reason this is in-platform

- **Embedding sync:** on every page write, the content is chunked (~1.5k-char
  paragraphs) and embedded with the existing OpenAI client
  (`text-embedding-3-small`, 1536 dims — same as schema embeddings) into
  `wiki_embeddings(page_id, tenant_id, chunk, embedding VECTOR(1536))`,
  replacing that page's prior chunks. Fail-open: a page saves fine even if
  embedding is unavailable; a reconciliation pass re-embeds un-embedded pages.
- **Retrieval:** `retrieve_wiki_context(query, tenant_id)` — cosine top-k on
  `wiki_embeddings`, the same contract as `retrieve_schema_context`
  (fail-open to `[]`, tenant GUC-bound connection).
- **Pipeline wiring:** `ChatService._step_nl2sql` gains a `## Tenant
  Knowledge` context section fed by retrieval (cached L1/L2 per
  query+tenant like schema context); the `chat_knowledge` router intent
  short-circuits to a wiki-search answer (retrieve → summarize, no SQL) when
  confidence is high. Wiki hits cite the source slug in the response.

This makes the wiki a first-class governance surface: knowledge that shapes
answers is versioned, attributed, and tenant-isolated — impossible with an
external wiki bolted on.

### 4. Frontend — `/wiki` page

Sidebar page tree (parent/child from `parent_slug`), markdown viewer
(`react-markdown` + `remark-gfm` are already dependencies), a split editor
(edit + live preview) for admins, and a history viewer with restore. Search
box hitting `/wiki/search`. Listed in chat-header navigation for all users;
edit controls hidden without the admin role.

### 5. Out of scope for v1 (noted for later phases)

Attachments/images, comments, per-space permissions, cross-page links with
backlinks, wiki export to PDF, WYSIWYG editor. The revision model and slug
hierarchy are chosen so none of these require migrations.

## Consequences

- Wiki writes cost one embedding call per save (Haiku-class pricing, optional
  dependency) — fail-open means the wiki is fully usable without
  `OPENAI_API_KEY`.
- `wiki_embeddings` is the second pgvector tenant table; its retrieval path
  reuses the proven schema-retrieval shape, so the NL2SQL prompt grows by one
  bounded context section.
- Tenant isolation is inherited, not added: the wiki is unreachable across
  tenants by construction (FORCE RLS), which is the entire reason to build it
  in-platform rather than integrate an external wiki.
