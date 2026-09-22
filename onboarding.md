# Tenant Onboarding Guide

Step-by-step setup for a **new tenant** on GenBI — from provisioning to your
first natural-language query. Two people are involved:

| Persona | Does | Needs |
|---|---|---|
| **Platform admin** | Provisions the tenant and its first admin user | Platform-admin access to the Admin portal |
| **Tenant admin** | Configures users, the AI provider key, and starts querying | The credentials the platform admin hands over |

> **Heads-up on ports:** this guide uses the demo defaults — frontend at
> `http://localhost:3003`, API at `http://localhost:8000`. Your deployment may
> publish different ports (`GENBI_HOST_FRONTEND_PORT`, …).

---

## Part 1 — Platform admin: provision the tenant

### 1.1 Get platform-admin access (once)

If nobody has it yet, grant it to an existing user from the repo root:

```bash
EMAIL=admin@genbi.local GENBI_SUPERUSER_PASSWORD='admin123' make admin-create
```

(Any existing user email works. The password prompt is only used when
creating a brand-new user; setting the env var just skips the prompt.)

### 1.2 Log in to the Admin portal

1. Open the frontend (`http://localhost:3003`) and sign in with the
   platform-admin account. The flag is minted **at login** — if you were
   already logged in, log out and back in to see the Admin link.
2. Open **Admin → Tenants**.

### 1.3 Create the tenant

Fill in **New tenant**:

| Field | Example | Notes |
|---|---|---|
| Name | `Acme Analytics` | Display name |
| Slug | `acme` | 3–50 chars, lowercase/digits/hyphens; used as the tenant handle |
| Admin email | `admin@acme.test` | Becomes the tenant's first admin user |
| Seed sample data | ✅ (default) | Loads a small demo dataset so Chat works immediately; uncheck for production tenants |

On submit the platform creates the tenant **and** its initial admin user —
transactionally.

> 🔐 **One-time password:** if you leave the password field empty, a random
> one is generated and shown **exactly once**. Copy it and hand it to the
  tenant admin securely — it is never stored or displayed again.

Optionally force-set the tenant's LLM provider now from
**Tenants → (tenant) → LLM provider** (the same BYOK form as Part 3, filled
in by the platform admin instead of the tenant). Most teams leave this to
the tenant admin.

---

## Part 2 — Tenant admin: first login

1. Open `http://localhost:3003/login`.
2. Sign in with the admin email + the password you were given.
3. You land on **Chat**. The left sidebar is the workspace:
   Chat · Explore · Reports · Dashboards · Wiki · Settings.

4. **Change the initial password** (if your platform admin set one manually):
   **Settings → Change password**. Tenant admins can also reset any team
   member's password later from **Settings → Users**.

---

## Part 3 — Tenant admin: connect your LLM key (BYOK)

By default every tenant runs on the **platform key**. Bring Your Own Key
switches your tenant to your own LLM account — validated, encrypted in the
database (pgcrypto), and never displayed again after saving.

1. Go to **Settings → AI Provider (bring your own key)**.
2. Fill the editor at the bottom of the card:

| Field | What to enter |
|---|---|
| Provider | **OpenAI format** for anything OpenAI-compatible (OpenAI, DeepSeek, Together, vLLM, LiteLLM…); **Anthropic native** for Claude |
| API key | Your key (`sk-…`). Write-only — re-entered on every save |
| Reasoning model | The stronger model, e.g. `deepseek-reasoner`, `claude-sonnet-4`, `o4-mini` |
| Fast model | The cheap/fast model used for routing, charts, narratives |
| Embedding model | **Leave empty unless your provider has an embeddings API.** If set, embeddings ride your key + base URL; if empty they stay on the platform OpenAI key |
| Base URL | Only for OpenAI-compatible gateways, e.g. `https://api.deepseek.com` (disabled for Anthropic) |

   **DeepSeek example:** Provider `OpenAI format` · Base URL
   `https://api.deepseek.com` · Reasoning `deepseek-reasoner` · Fast
   `deepseek-chat` · Embedding **empty** (DeepSeek has no embeddings API).

3. Click **Validate** — a live 1-token ping against your fast model. Fix any
   error it reports before saving.
4. Click **Save**.

> 💡 **The Save/Validate buttons look dead?** They stay grayed out until you
> type the API key into the key field — it is treated as re-entered on every
> save. Type the key first; the buttons enable.

Two things to know after saving:

- **No silent fallback.** Once active, *all* of the tenant's LLM traffic uses
  your key. If the key breaks, chat surfaces an `LLM_BYOK_MISCONFIGURED`
  error instead of quietly switching back — fix or **Disable**/**Revert to
  platform key** on the same card.
- The card now shows the provider, key last-4, version, and status. The API
  equivalent is `PUT /api/v1/settings/llm` (see
  [docs/api-reference.md](docs/api-reference.md)).

---

## Part 4 — Tenant admin: add your team

**Settings → Users** (tenant admins only):

| Role | Can do |
|---|---|
| `admin` | Everything below + manage users + configure the AI provider |
| `user` | Chat, reports, dashboards, wiki |
| `viewer` | Read-only lookups |

**Create user** takes an email and a password (min 8 chars) — hand it over
securely; it is not shown again.

---

## Part 5 — Platform admin (optional): sharpen NL2SQL grounding

Chat works out of the box: when vector embeddings aren't available, schema
retrieval falls back to **lexical ranking** over the table metadata, and the
NL2SQL agent additionally grounds on Cube metric definitions.

For full **semantic** retrieval (better matches on paraphrases), backfill
pgvector embeddings for the tenant — requires a real `OPENAI_API_KEY` in
`backend/.env`:

```bash
docker compose -f infra/docker-compose.dev.yml exec -T \
  -e PYTHONPATH=/app backend uv run python scripts/embed_schema.py \
  --tenant-id <tenant-uuid> --examples \
  --examples-file /app/tests/evals/nl2sql_golden.json
```

Find the tenant UUID in **Admin → Tenants**. `--examples` also seeds the
golden NL→SQL few-shot pairs. Re-run any time the schema changes; it is
idempotent.

---

## Part 6 — Tenant admin (optional): capture business context in the Wiki

**Wiki** pages (markdown) feed the NL2SQL agent real business context —
definitions like *"Revenue = gross bookings net of refunds"* measurably
improve generated SQL. A handful of well-titled pages covering your core
metrics and naming quirks is usually enough.

---

## Part 7 — Your first query

1. Open **Chat** and ask something concrete:
   *"Show me total revenue by region for 2025"*.
2. The pipeline streams its stages: generated SQL → validation → executed
   rows → chart → written narrative. Expand the SQL block to see exactly what
   ran; every call is audit-logged (tokens, latency, model).
3. Follow up conversationally (*"now break that down by product"*) — the
   conversation keeps context.
4. Pin results into **Reports** and **Dashboards** when you want them kept.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Validate/Save grayed out | API-key field empty (write-only by design) | Type the key; buttons enable |
| `… rejected the credentials` on Validate | Wrong key or wrong Base URL | Re-check key/provider/base URL |
| Chat errors with `LLM_BYOK_MISCONFIGURED` | Saved key stopped working | Fix the key in Settings, or **Disable**/**Revert to platform key** |
| Chat works but tables/columns look guessed | No schema grounding — lexical fallback ranked loosely | Run the Part 5 embedding backfill |
| `<Agent> not registered` warnings | Stale backend predating the agent registry fix | Restart the backend container |
| New tenant admin can't see Admin | Platform-admin flag is minted at login | Log out and back in |
| Login 429 | 5 failed attempts trigger throttling | Wait or have the password reset |

---

*Platform operator? [README.md](README.md) covers stack setup;
[DEMO.md](DEMO.md) covers the demo lifecycle.*
