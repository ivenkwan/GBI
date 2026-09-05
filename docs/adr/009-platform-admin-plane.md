# ADR 009: Platform admin plane — superusers, tenant lifecycle, and the control/data plane split

- **Status:** Proposed (2026-09-05, design phase — not yet built)
- **Context:** Multi-tenancy hardening — admin portal, superuser model, tenant provisioning
- **Related:** ADR 006 (enforced RLS roles), ADR 008 (per-tenant Cube data path),
  `infra/postgres/init.sql`, `backend/app/core/auth.py`, `backend/app/api/v1/auth.py`,
  Phases 21–24 in `todo.md`

## Context

Tenancy today is **data-plane only and fully enforced**: every tenant-scoped table
carries FORCE RLS keyed on the `app.current_tenant_id` GUC (ADR 006), the runtime
connects as `genbi_app`, login as `genbi_auth`, and Cube isolates per-tenant
orchestrators via the JWT `tenantId` claim (ADR 008). But the **control plane does
not exist**:

- Tenants are rows inserted by hand (`init.sql` / SQL). No provisioning, rename,
  suspend, or deprovisioning path; no lifecycle state.
- Users are seeded the same way. No create/update/disable/delete API; password
  resets are a SQL exercise.
- There is no platform-scope identity at all. The seeded `admin@genbi.local`
  carries `["admin","user"]` in the tenant-scoped `roles` JSONB — that role means
  "admin *of that tenant*" in every place roles are consulted, and nothing can
  administer the platform itself.
- The frontend has no admin surface (the Settings button is a no-op).

The request: a platform-wide admin portal (per-tenant setup and maintenance,
superuser registration and related tasks) plus per-tenant user management and a
tenant knowledge base (ADR 010). This ADR covers the identity, authorization,
and tenant-lifecycle design those features need.

## Decision

### 1. Two scopes of authority, two mechanisms

| Scope | Mechanism | Granted by | Checked by |
|---|---|---|---|
| Tenant-scoped roles (`user`, `admin`, later `editor`) | `users.roles` JSONB (unchanged) | Tenant admins / platform admins | Existing role checks (validation agent, future wiki guards) |
| Platform superuser | `platform_admins` grant table (new) | Existing platform admins | `require_platform_admin` dependency |

We deliberately do **not** add a `"superadmin"` string to `users.roles`. The roles
array is a tenant claim — it rides the JWT inside `tenant_id` semantics and is
consumed by tenant-scoped logic. Overloading it with a platform-wide role would
let a role check in one scope accidentally trust an escalation from the other.
A separate grant table also gives revocation with history (`granted_at/by`,
`revoked_at/by`) and keeps a superuser's *ordinary* identity in their home
tenant — a platform admin is still a tenant user for day-to-day work.

`platform_admins` schema: `user_id UUID PK REFERENCES users(id)`,
`granted_by UUID`, `granted_at TIMESTAMPTZ`, `revoked_at TIMESTAMPTZ NULLABLE`,
`revoked_by UUID NULLABLE`. A user is an active superuser iff they have a row
with `revoked_at IS NULL`.

### 2. JWT: a claim for routing, the table for truth

Login consults `platform_admins` (via `genbi_admin`, see §3) and mints
`platform_admin: true` into the JWT alongside the existing claims. The
`require_platform_admin` FastAPI dependency:

1. verifies the claim (fast 401/403 path), then
2. re-checks the grant table through a 60-second L1/L2-cached lookup
   (`platform_admin:{user_id}`), so a revoked superuser's unexpired token loses
   power within a minute instead of at token expiry.

Tenant suspension uses the same pattern: `get_current_user` gains a cached
`tenant:{id}:status` lookup; suspended tenants get `403 TENANT_SUSPENDED` on
every authenticated endpoint, not just login.

### 3. A third dedicated role: `genbi_admin` (control-plane DSN)

Following the ADR 006 pattern — least privilege per connection purpose — the
admin services connect as a new non-superuser LOGIN role:

- **`genbi_admin`** (`DATABASE_URL_ADMIN`, derived from `DATABASE_URL` when
  unset): DML on the control-plane tables (`tenants`, `users`,
  `platform_admins`, `admin_audit`) and `SELECT` on `audit_log`, with
  permissive RLS policies scoped `TO genbi_admin` on exactly those tables.
  It can read **no business data** — analytics, conversations, reports,
  dashboards, wiki stay GUC-scoped. A superuser debugging a tenant's report
  does so through the tenant's own tools, not by fiat.

Cross-tenant maintenance that genuinely needs business rows (e.g. per-tenant
row counts for the portal) uses short-lived `genbi_app` connections with the
tenant GUC set per tenant — the same discipline as
`scripts/db_admin.py` and the report scheduler's owner path.

### 4. Tenant lifecycle

`tenants` gains `slug` (unique short code for URLs/display), `status`
(`active` | `suspended`, default `active`), and `settings JSONB` (per-tenant
feature flags — e.g. scheduler off for a trial tenant — read at request time,
cached like status).

- **Provisioning** (`POST /admin/tenants`) is transactional: insert tenant +
  initial tenant-admin user (temp password shown once to the operator) +
  optional sample-data seed. Nothing to provision in Cube — orchestrators spin
  up per `tenantId` on demand (ADR 008). Lineage graph and caches are
  tenant-agnostic or keyed and need no action.
- **Suspension** flips status; enforcement is the cached check in §2.
  Data is untouched — suspension is reversible by design.
- **Decommission** (`DELETE /admin/tenants/{id}`) is guarded: requires
  `confirm=yes` query flag, refuses while the tenant has users (force-delete
  cascades conversations/reports/dashboards/wiki via FK `ON DELETE CASCADE`;
  audit rows are retained — they carry `tenant_id` without FK by design).
  Documented as destructive.

### 5. Superuser bootstrap — governed, not open signup

Registration is **not** self-service (this is a governed enterprise platform;
open signup would contradict the entire RLS posture). Bootstrap paths:

1. First run: `GENBI_SUPERUSER_EMAIL` / `GENBI_SUPERUSER_PASSWORD` env (dev
   compose + docs) applied by a startup-safe script (`scripts/create_admin.py`,
   owner role, idempotent) — the analogue of today's seeded dev admin.
2. Thereafter: existing superusers grant/revoke via `POST/DELETE /admin/admins`
   from the portal.

Every admin mutation writes an `admin_audit` row (new table — `audit_log` is
LLM-call-shaped and the wrong shape for admin actions):
`actor_user_id, action, target_type, target_id, detail JSONB, created_at`,
written via the GUC-writer pattern, fail-open for reads, raise-on-write.

### 6. Admin API surface (summary — full spec in `docs/api-reference.md`)

```
GET    /admin/stats                    platform counters (tenants, users, calls)
GET    /admin/tenants                 list + per-tenant counters
POST   /admin/tenants                 provision (name, slug, admin email, temp password)
GET    /admin/tenants/{id}            detail: users, schedules, counts, recent audit
PATCH  /admin/tenants/{id}            rename / suspend / activate / settings
DELETE /admin/tenants/{id}?confirm=yes  decommission (guarded)
GET    /admin/admins                  active superusers + grant history
POST   /admin/admins                  grant (by user id or email)
DELETE /admin/admins/{user_id}        revoke
GET    /admin/audit                   admin-action feed (filter by actor/target/tenant)
```

All guarded by `require_platform_admin`; all audited.

### 7. Frontend: `/admin` area

A superuser-guarded route group (`/admin`, `/admin/tenants`,
`/admin/tenants/[id]`, `/admin/admins`, `/admin/audit`) reusing the existing
shell idioms: `AuthGuard` + a `PlatformAdminGuard` that checks the token claim,
sidebar navigation, shadcn tables. Non-superusers never see admin navigation
(chat header shows a Shield icon only when the claim is present).

## Consequences

- Three purpose-built DB roles (`genbi_app`, `genbi_auth`, `genbi_admin`) each
  with a narrow, auditable blast radius; the owner role (`genbi`) remains for
  migrations and bootstrap only — unchanged from ADR 006.
- Revocation latency for superusers is bounded by the 60s cache, not the JWT
  lifetime; suspension similarly. Acceptable for this threat model (documented;
  tokens are 60-minute anyway).
- The `users_login_lookup` carve-out for `genbi_auth` is unchanged; login
  additionally reads `platform_admins` + `tenants.status` — these joins run on
  the `genbi_admin`-granted tables, so **login's DSN moves to `genbi_admin`**
  (it supersedes `genbi_auth`'s single-table scope; `genbi_auth` is retired in
  the same migration to avoid two near-identical login roles).
- RLS policies for new tables continue the paired
  `infra/postgres/rls/*.sql` seam (make migrate / CI), per the Phase 19
  convention; Alembic carries schema via structured ops only.
- Destructive decommission is opt-in and irreversible — surfaced as a typed
  confirm in the portal, not just a query flag.
