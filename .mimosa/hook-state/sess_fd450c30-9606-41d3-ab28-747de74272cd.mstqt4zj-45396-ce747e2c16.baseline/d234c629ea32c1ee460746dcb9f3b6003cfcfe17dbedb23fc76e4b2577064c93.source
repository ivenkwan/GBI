#!/usr/bin/env bash
# Smoke test for a running GenBI stack. Checks each service is reachable and
# wired correctly. Exits non-zero on first failure with a readable message.
#
# Usage: scripts/verify.sh
# Assumes the dev stack is up (docker compose -f infra/docker-compose.dev.yml up -d)

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "GenBI stack verification"
echo "────────────────────────"

# --- helpers -----------------------------------------------------------------
# Run a psql command inside the postgres container.
psql_exec() {
  docker exec genbi-postgres psql -U genbi -d genbi -tA -c "$1" 2>/dev/null
}

# Same, but stderr kept — expected-failure checks need the error text.
psql_full() {
  docker exec genbi-postgres psql -U genbi -d genbi -tA -c "$1" 2>&1
}

# --- 1. Backend liveness -----------------------------------------------------
if curl -sf http://localhost:8000/api/v1/health >/dev/null 2>&1; then
  ok "backend liveness (GET /api/v1/health → 200)"
else
  bad "backend liveness — is the backend up on :8000?"
fi

# --- 2. Backend readiness (real DB + Redis pings) ----------------------------
READY=$(curl -sf http://localhost:8000/api/v1/health/ready 2>/dev/null || true)
if echo "$READY" | grep -q '"status":"ready"'; then
  ok "backend readiness (DB + Redis reachable, status=ready)"
elif echo "$READY" | grep -q '"status":"degraded"'; then
  bad "backend readiness DEGRADED: $(echo "$READY" | tr -d '\n')"
else
  bad "backend readiness — /health/ready did not return ready status"
fi

# --- 3. Cube -----------------------------------------------------------------
if curl -sf http://localhost:4000/ >/dev/null 2>&1 \
   || curl -sf http://localhost:4000/cubejs-api/v1/load >/dev/null 2>&1; then
  ok "cube reachable on :4000"
else
  bad "cube — not responding on :4000"
fi

# --- 4. Redis ----------------------------------------------------------------
if docker exec genbi-redis redis-cli ping 2>/dev/null | grep -q PONG; then
  ok "redis ping → PONG"
else
  bad "redis — no PONG (is genbi-redis running?)"
fi

# --- 5. Postgres: seed + AGE -------------------------------------------------
TENANT_COUNT="$(psql_exec 'SELECT count(*) FROM tenants;' 2>/dev/null || echo '0')"
if [[ "${TENANT_COUNT:-0}" -ge 1 ]]; then
  ok "postgres — seed tenant present ($TENANT_COUNT tenant(s))"
else
  bad "postgres — no tenants (init.sql / migrations not applied?)"
fi

# AGE check (optional — degrades gracefully if disabled)
AGE_GRAPH="$(psql_exec "SELECT count(*) FROM ag_catalog.ag_graph WHERE name='genbi_graph';" 2>/dev/null || echo '')"
if [[ "${AGE_GRAPH:-}" == "1" ]]; then
  ok "postgres — Apache AGE graph 'genbi_graph' exists"
elif [[ -z "${AGE_GRAPH:-}" ]]; then
  echo "  ⚠️  Apache AGE not available — lineage graph disabled (GENBI_ENABLE_AGE controls this)"
else
  bad "postgres — AGE present but 'genbi_graph' missing (run init_age_graph)"
fi

# --- 6. RLS enforcement (Phase 8b: runtime roles are actually bound) --------
APP_USERS="$(psql_exec "SET ROLE genbi_app; SELECT count(*) FROM users;" || true)"
if [[ "${APP_USERS:-x}" == "0" ]]; then
  ok "RLS enforced — genbi_app sees 0 users without tenant GUC"
else
  bad "RLS NOT enforced — genbi_app saw ${APP_USERS:-<error>} users without GUC (roles migrated?)"
fi

AUTH_USERS="$(psql_exec "SET ROLE genbi_auth; SELECT count(*) FROM users;" || true)"
if [[ "${AUTH_USERS:-x}" =~ ^[0-9]+$ ]] && [[ "${AUTH_USERS}" -ge 1 ]]; then
  ok "auth role can look up users ($AUTH_USERS row(s), cross-tenant by design)"
else
  bad "auth role cannot read users (login path broken — Alembic 0002 applied?)"
fi

AUTH_AUDIT="$(psql_full "SET ROLE genbi_auth; SELECT count(*) FROM audit_log;" || true)"
if echo "$AUTH_AUDIT" | grep -q "permission denied"; then
  ok "auth role is denied on non-users tables (audit_log)"
else
  bad "auth role could read audit_log — its grants are too broad"
fi

# --- 6b. Auth: login issues a JWT (needed by the checks below) ---------------
LOGIN_RESP="$(curl -sf -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@genbi.local","password":"admin123"}' 2>/dev/null || true)"
if echo "$LOGIN_RESP" | grep -q '"access_token"'; then
  ok "auth — login issues a JWT for the seeded dev user"
else
  bad "auth — /auth/login failed (seed user only exists on fresh volumes; try make reset)"
fi

# --- 6c. Tenant-scoped metric query (Phase 10: JWT → Cube → GUC → RLS) --------
TOKEN="$(echo "$LOGIN_RESP" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')"
if [[ -n "$TOKEN" ]]; then
  METRIC_RESP="$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/v1/metrics/query \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"measures":["Sales.revenue_total"],"limit":5}' 2>/dev/null || echo '000')"
  METRIC_BODY="$(curl -s -X POST http://localhost:8000/api/v1/metrics/query \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"measures":["Sales.revenue_total"],"limit":5}' 2>/dev/null || true)"
  if [[ "$METRIC_RESP" == "200" ]] && echo "$METRIC_BODY" | grep -q '"data":\[{'; then
    ok "tenant-scoped metric query returns rows (JWT→Cube→GUC→RLS chain live)"
  elif [[ "$METRIC_RESP" == "200" ]]; then
    echo "  ⚠️  metric query OK but 0 rows — tenant has no seed data (make seed)?"
  else
    bad "metric query failed (HTTP $METRIC_RESP) — Cube tenant path broken?"
  fi
else
  echo "  ℹ️  skipping metric query check (no token — login failed above)"
fi

# --- 6d. NL2SQL schema grounding (Phase 11) ------------------------------------
EMBED_COUNT="$(psql_exec 'SELECT count(*) FROM schema_embeddings;' || echo 0)"
if [[ "${EMBED_COUNT:-0}" =~ ^[0-9]+$ ]] && [[ "${EMBED_COUNT}" -ge 1 ]]; then
  ok "schema embeddings present ($EMBED_COUNT tables) — NL2SQL schema grounding armed"
else
  echo "  ℹ️  schema_embeddings empty — run scripts/embed_schema.py to arm schema grounding"
fi

# --- 6e. Audit trail (Phase 12) -------------------------------------------------
AUDIT_ROWS="$(psql_exec 'SELECT count(*) FROM audit_log;' || echo 0)"
if [[ "${AUDIT_ROWS:-0}" =~ ^[0-9]+$ ]] && [[ "${AUDIT_ROWS}" -ge 1 ]]; then
  ok "audit trail active ($AUDIT_ROWS LLM-call entries recorded)"
else
  echo "  ℹ️  audit_log empty — rows appear after the first LLM-backed chat query"
fi

# --- 8. Frontend (optional — requires Node/pnpm toolchain to build) ----------
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 2>/dev/null || echo '000')"
if [[ "${HTTP_CODE}" =~ ^([23][0-9][0-9])$ ]]; then
  ok "frontend served on :3000 (HTTP $HTTP_CODE)"
else
  echo "  ℹ️  frontend not reachable on :3000 (requires Node/pnpm to build; optional)"
fi

# --- 9. Prometheus (optional) ------------------------------------------------
if curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1; then
  ok "prometheus healthy on :9090"
else
  echo "  ℹ️  prometheus not reachable on :9090 (optional)"
fi

echo "────────────────────────"
echo "Result: $PASS passed, $FAIL failed"
exit $(( FAIL > 0 ? 1 : 0 ))
