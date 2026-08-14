# ADR 006: Enforced tenant isolation via dedicated database roles

- **Status:** Accepted (2026-08-15)
- **Context:** Phase 8b — Multi-tenant RLS enforcement
- **Related:** `infra/postgres/init.sql`, Alembic revisions `0002_app_roles` and
  `0003_analytics`, `backend/app/db/session.py`, `docs/data-layer.md`

## Context

Since Phase 6 the schema has had `ENABLE`/`FORCE ROW LEVEL SECURITY` plus a
`tenant_isolation` policy on every tenant-scoped table, keyed on the
`app.current_tenant_id` session GUC that `PostgreSQLConnector` sets per
transaction. The fine print: **RLS never constrains superusers**, and the
backend connected as `POSTGRES_USER` (`genbi`) — a superuser in the official
Postgres image. Tenant isolation was configured but never enforced; any code
path (or SQL injection) that skipped the GUC would read cross-tenant data.

A second gap: the 10 analytics tables that chat queries actually read
(`sales`, `orders`, …) were not RLS-enrolled at all — only the 5 metadata
tables were — so the connector's GUC had no effect on query results.

The login path added in Phase 8a complicated the fix: login must find a user
by email *across* tenants (to support per-tenant credentials and
disambiguation), which a per-tenant RLS policy forbids by design.

## Decision

1. **Two dedicated non-superuser LOGIN roles** (Alembic `0002`, mirrored in
   `init.sql` for fresh volumes; fixed dev passwords, rotate in production):
   - `genbi_app` — the runtime role for the ORM engine and the query
     connector (`DATABASE_URL`). No superuser, no `BYPASSRLS`, no `CREATE`;
     granted exactly the DML it needs on the tenant tables and `SELECT` on
     analytics tables. Every RLS policy applies to it.
   - `genbi_auth` — the login endpoint's role (`DATABASE_URL_AUTH`, derived
     from `DATABASE_URL` when unset). `SELECT` on `users` only, plus a
     permissive RLS policy scoped `TO genbi_auth`
     (`users_login_lookup ... USING (true)`) — the single, auditable
     carve-out that a credential lookup requires. It can read nothing else
     and write nothing.
2. **Analytics tables join the RLS regime** (Alembic `0003`): the 10 seed
   tables (renamed `users` → `web_users` to stop shadowing the app-login
   table) get the same FORCE RLS + `tenant_isolation` policy. The connector
   already set the GUC, so chat queries keep working — but a missing GUC now
   yields zero rows instead of cross-tenant data.
3. **Owner credentials are exiled to `DATABASE_URL_SYNC`**, used only by
   Alembic and admin scripts (`scripts/db_admin.py`). Those scripts connect
   as the owner *and* set the tenant GUC, because FORCE RLS binds the owner
   too.
4. **Enforcement is tested, not assumed**: `tests/api/test_tenant_isolation.py`
   connects with the real roles and asserts cross-tenant invisibility,
   forged-tenant INSERT rejection, no-GUC blindness, and the genbi_auth
   carve-out's exact boundaries. `scripts/verify.sh` checks the same in the
   running stack.

## Consequences

- A compromised or buggy backend can no longer read another tenant's rows by
  forgetting the GUC; it can only see rows the policy allows.
- `genbi_auth` remains a cross-tenant read oracle on `users` by necessity
  (login); the endpoint returns indistinguishable 401s and is the natural
  place for future rate limiting.
- Writing to any tenant table through the ORM now requires setting the GUC
  on the session (no ORM writers exist yet; the isolation tests and
  `db_admin.set_tenant_guc` are the pattern to copy).
- Alembic stays on `DATABASE_URL_SYNC`; migrations that create roles or
  policies must keep running as the owner.
- AGE lineage code (`graph_schema.py`) remains dead code with
  f-string-interpolated Cypher; parameterizing it is a tracked follow-up
  before it can be wired to the runtime role.
