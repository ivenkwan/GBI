# ADR 011: Tenant BYOK — per-tenant LLM providers with tenant-held API keys

- **Status:** Proposed (2026-09-05, design phase — not yet built)
- **Context:** Bring-your-own-key LLM access per tenant, supporting both the
  Anthropic native endpoint format and the OpenAI API format
- **Related:** ADR 009 (admin plane — where BYOK is configured and audited),
  ADR 010 (wiki embeddings consume the embedding resolution), ADR 002 (agents
  all route through the central LLM client), `backend/app/core/llm_client.py`,
  `backend/app/core/embeddings.py`, Phases 25–26 in `todo.md`

## Context

Every LLM call today runs on one platform-wide Anthropic key
(`ANTHROPIC_API_KEY`) with platform-wide model names
(`LLM_REASONING_MODEL` / `LLM_FAST_MODEL`); embeddings run on one
platform-wide OpenAI key. For multi-tenant operations this is wrong on three
axes: tenants with existing OpenAI/Anthropic agreements want to spend their
own commitments; the platform operator carries everyone's token bill and
rate limits; and data-governance-minded tenants want their prompts hitting
*their* account, not the operator's.

Two facts make BYOK cheap to add correctly:

1. **All agents already route through `LLMClient.invoke()`, and every call
   already carries `tenant_id`** (it was plumbed for audit). Resolution can
   happen inside the client — zero agent changes.
2. `TENANT_ENCRYPTION_KEY` already exists in settings (currently unused) —
   the encryption anchor is waiting.

The requirement adds a second axis: both **Anthropic-native** (`/v1/messages`,
system prompt separate, thinking mode, `max_tokens` required) and
**OpenAI-format** (`/v1/chat/completions`, role-tagged messages,
`response_format: json_object`) endpoints must be supported, including
OpenAI-compatible gateways via a custom base URL.

## Decision

### 1. A resolution layer inside the existing client — not client sprawl

`invoke()` keeps its exact signature. Internally it first resolves the
tenant's effective LLM configuration:

```
resolve_llm(tenant_id) -> ResolvedLLM(
    provider: "anthropic" | "openai",
    base_url: str | None,          # optional gateway override
    api_key: str,                  # plaintext, in-memory only
    reasoning_model: str, fast_model: str,
    embedding_model: str | None,   # openai provider only
    source: "tenant" | "platform", # for audit attribution
    key_version: int | None,       # tenant rotations only
)
```

No tenant configuration → platform defaults (today's behavior, unchanged).
The resolution result is cached in L1 for 60s keyed
`byok:{tenant_id}:{key_version}` — rotation bumps `key_version`, so stale
plaintext keys age out of memory within the TTL and saves invalidate
explicitly. Plaintext keys exist only in that cache entry and the outbound
HTTP call; never in logs (log kwargs are an allowlist), never in audit, never
in API responses.

### 2. Provider adapters with a normalized contract

`app/llm/providers/`:

- `base.py` — the adapter contract: `invoke(messages, system, opts) -> raw`
  producing `(content, input_tokens, output_tokens)` + provider-specific
  error typing, so retry/budget/JSON-extraction stay in `LLMClient` exactly
  as today (`_extract_json` is provider-agnostic and keeps working).
- `anthropic_provider.py` — today's `langchain-anthropic` path, lifted
  unchanged (thinking mode via `model_kwargs`, `max_tokens` semantics).
- `openai_provider.py` — chat completions via the existing `openai` SDK
  dependency, `base_url` override honored, `response_format={"type":
  "json_object"}` mapped from `opts.response_format == "json"` (the shared
  extractor remains the fallback). `opts.thinking` is a documented no-op:
  OpenAI reasoning is selected by model name (e.g. `o4-mini`), not a flag.

Adapter parity is enforced by a shared test matrix (string + message-list
inputs, JSON mode, token accounting, error propagation).

### 3. Storage: a dedicated, secret-bearing table

`tenant_llm_providers` — one active provider per tenant (PK `tenant_id`):

| Column | Notes |
|---|---|
| `tenant_id UUID PK` | FK → tenants |
| `provider VARCHAR(20)` | `anthropic` \| `openai` (CHECK) |
| `base_url TEXT NULL` | OpenAI-compatible gateways / proxies |
| `reasoning_model`, `fast_model VARCHAR(100)` | per-tenant model roles |
| `embedding_model VARCHAR(100) NULL` | used only when provider = openai |
| `api_key_enc TEXT` | pgcrypto armored ciphertext — never plaintext |
| `key_last4 VARCHAR(4)` | for masked display |
| `key_version INTEGER` | bumped on every write; cache invalidation key |
| `status VARCHAR(20)` | `active` \| `disabled` (kill switch without deleting) |
| `updated_by UUID`, timestamps | |

Standard tenant RLS recipe via the paired `rls/*.sql` seam. The secret lives
in **its own table, never in `tenants.settings`** — settings JSONB is
readable through generic settings surfaces; a secret-bearing table gets its
own narrow API that can never echo the key.

### 4. Encryption: pgcrypto behind SECURITY DEFINER functions

`infra/postgres/byok-crypto.sql` creates schema `app_crypto` with
`encrypt(p_key text, p_plaintext text)` / `decrypt(p_key text, p_ciphertext
text)` wrapping `pgcrypto.pgp_sym_encrypt/decrypt`. The key arrives as the
`$1` bind parameter from `TENANT_ENCRYPTION_KEY` — the key is in no DDL, no
SQL literal, no log, and Python never constructs ciphertext. This is the
same static-SQL/DB-function seam the AGE lineage functions use (which also
keeps the security write-gate happy). Writes/reads of the config go through
`genbi_app` with the tenant GUC; `pgcrypto` ships in the Postgres contrib
layer of the existing image.

Fail-fast: any BYOK write or tenant-routed call refuses with
`BYOK_NOT_CONFIGURED` when the platform has no `TENANT_ENCRYPTION_KEY`.

### 5. No silent fallback to the platform key — deliberate

When a tenant configuration exists, its provider/key is used, full stop. If
the call fails with provider auth errors (401/403), the error surfaces to
the caller (chat: graceful degradation with `LLM_BYOK_MISCONFIGURED`
warning; settings API: 400 with the provider's sanitized message). Falling
back to the platform key would (a) mask a broken/expired tenant key as
"working" and (b) route a tenant's prompts and spend onto the operator's
account without consent. The platform key is used **only** when no tenant
configuration exists. `status: disabled` is the explicit "revert" switch
(and `DELETE /settings/llm` removes the config).

### 6. Save-time validation, masked reads

`PUT /settings/llm` runs a live 1-token ping against the provider (Anthropic:
`max_tokens=1`; OpenAI: `max_tokens=1`) before accepting the config; a
separate `POST /settings/llm/validate` tests without saving. Reads — tenant
self-service and admin — return everything **except** the key:
provider/base_url/models/`key_last4`/`key_version`/`status`/`updated_at`.

### 7. API surface (summary — full spec in `docs/api-reference.md`)

```
GET    /settings/llm                     tenant's config (masked)
PUT    /settings/llm                     create/replace (validates, bumps key_version)
POST   /settings/llm/validate            test a candidate config without saving
DELETE /settings/llm                     revert to the platform key
GET    /admin/tenants/{id}/llm           masked view + usage-by-model  (superuser)
PUT    /admin/tenants/{id}/llm           force-set on behalf of a tenant (superuser)
```

Write guards: tenant `admin` role for `/settings/llm`; platform superuser
for the admin variants (ADR 009 guards). Every BYOK mutation writes an
`admin_audit`-style audit entry (actor, tenant, action, key_version).

### 8. Audit and cost attribution

`audit_log` gains `provider VARCHAR(20)`, `key_source VARCHAR(10)`
(`tenant` | `platform`), and `key_version INTEGER NULL` (small migration;
`tenant_id` was already there). The audit callback receives them from the
resolved config. This makes per-tenant spend computable from the existing
audit trail (group by tenant × provider × model) — surfaced in the admin
portal (Phase 26) with no new metering infrastructure.

### 9. Embeddings boundary (v1)

Anthropic publishes no embeddings API, so embeddings cannot BYOK to an
Anthropic tenant. When `provider = openai` and `embedding_model` is set,
`core/embeddings.py` resolves the tenant key (same resolver) and uses it;
otherwise the platform OpenAI key stays in force. Fail-open unchanged.

## Consequences

- Agent code, prompts, retry/budget/JSON-extraction logic are untouched;
  the blast radius of BYOK is one resolver + two adapters + one table.
- Tenant keys are encrypted at rest (pgcrypto, key only in env + bind
  params), write-only via API, absent from logs and audit; rotation
  invalidates cached plaintext within 60s.
- A tenant with a broken key gets loud errors, not silent platform spend —
  the correct governance default for a multi-tenant product.
- Per-tenant rate limits/quotas (e.g. cap a tenant's daily tokens) are
  deliberately out of scope; `tenants.settings` (ADR 009) is the hook when
  needed.
- Dependency note: no new Python dependencies — `langchain-anthropic`,
  `openai`, and Postgres contrib `pgcrypto` are already in the stack.
