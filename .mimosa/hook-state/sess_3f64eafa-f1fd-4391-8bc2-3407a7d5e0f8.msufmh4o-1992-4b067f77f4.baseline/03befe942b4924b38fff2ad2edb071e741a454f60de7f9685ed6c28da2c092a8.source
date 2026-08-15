#!/usr/bin/env bash
# Generate backend/.env and semantic/cube/.env from templates with random
# secrets. Idempotent: refuses to overwrite existing files unless --force.
#
# Usage:
#   scripts/gen-env.sh           # write missing files only
#   scripts/gen-env.sh --force   # overwrite existing files
#
# Designed to be safe to re-run (make secrets). The ANTHROPIC_API_KEY is left
# as a placeholder — it requires a real key and is the one secret we cannot
# generate. A warning is printed if it is still a placeholder.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# --- helpers -----------------------------------------------------------------

rand_hex() { openssl rand -hex "$1"; }

gen_fernet() {
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
    || python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
}

# Emit a line only if the key isn't already going to be replaced. We rewrite
# the whole file from the template each time.

# Returns 0 (true) when we SHOULD write (file missing, or --force).
should_write() {
  local target="$1"
  if [[ "$FORCE" -eq 1 ]]; then
    return 0
  fi
  if [[ -f "$target" ]]; then
    echo "  exists: $target (use --force to overwrite)"
    return 1
  fi
  return 0
}

# --- backend/.env ------------------------------------------------------------

BACKEND_ENV="$REPO_ROOT/backend/.env"
TEMPLATE="$REPO_ROOT/.env.example"

if should_write "$BACKEND_ENV"; then
  if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: template $TEMPLATE not found" >&2; exit 1
  fi

  JWT_SECRET="$(rand_hex 32)"
  CUBE_SECRET="$(rand_hex 32)"
  TENANT_KEY="$(gen_fernet)"
  # Owner credentials (migrations/admin only). The runtime DATABASE_URL uses
  # the RLS-bound genbi_app role, and the login path genbi_auth — fixed dev
  # defaults matching infra/postgres/init.sql + Alembic 0002_app_roles.
  # Rotate in production.
  PG_USER="genbi"
  PG_PASS="genbi"
  PG_DB="genbi"

  # Substitute placeholders. DATABASE_URL/REDIS_URL use the compose service
  # names ('postgres', 'redis') as hosts — the .env file is consumed by the
  # backend container, where 'localhost' would mean the container itself.
  # Host-based (non-Docker) dev should override these via a local .env override.
  sed \
    -e "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=sk-ant-REPLACE-ME|" \
    -e "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=sk-REPLACE-ME|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://genbi_app:genbi_app@postgres:5432/${PG_DB}|" \
    -e "s|^DATABASE_URL_AUTH=.*|DATABASE_URL_AUTH=postgresql+asyncpg://genbi_auth:genbi_auth@postgres:5432/${PG_DB}|" \
    -e "s|^DATABASE_URL_SYNC=.*|DATABASE_URL_SYNC=postgresql://${PG_USER}:${PG_PASS}@postgres:5432/${PG_DB}|" \
    -e "s|^REDIS_URL=.*|REDIS_URL=redis://redis:6379/0|" \
    -e "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET}|" \
    -e "s|^CUBE_API_SECRET=.*|CUBE_API_SECRET=${CUBE_SECRET}|" \
    -e "s|^TENANT_ENCRYPTION_KEY=.*|TENANT_ENCRYPTION_KEY=${TENANT_KEY}|" \
    "$TEMPLATE" > "$BACKEND_ENV"

  echo "  wrote:  $BACKEND_ENV"
  echo "           (JWT_SECRET_KEY, CUBE_API_SECRET, TENANT_ENCRYPTION_KEY randomized)"
  if grep -q "REPLACE-ME" "$BACKEND_ENV"; then
    echo "  ⚠️  ANTHROPIC_API_KEY / OPENAI_API_KEY are placeholders — set them before running LLM/embedding features."
  fi
fi

# --- semantic/cube/.env ------------------------------------------------------

CUBE_ENV="$REPO_ROOT/semantic/cube/.env"
CUBE_TEMPLATE="$REPO_ROOT/semantic/cube/.env.example"

if should_write "$CUBE_ENV"; then
  if [[ ! -f "$CUBE_TEMPLATE" ]]; then
    echo "ERROR: template $CUBE_TEMPLATE not found" >&2; exit 1
  fi

  # Reuse the CUBE_API_SECRET generated above so backend and Cube agree.
  # If backend/.env already existed (not rewritten this run), read it from there.
  if [[ -z "${CUBE_SECRET:-}" ]]; then
    CUBE_SECRET="$(grep '^CUBE_API_SECRET=' "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || true)"
  fi
  if [[ -z "${CUBE_SECRET}" ]]; then
    CUBE_SECRET="$(rand_hex 32)"
  fi

  PG_PASS="genbi"
  # cube_reader: read-only role created by infra/postgres/init.sql. Dev
  # default password — rotate in production.
  sed \
    -e "s|^CUBEJS_DB_HOST=.*|CUBEJS_DB_HOST=postgres|" \
    -e "s|^CUBEJS_DB_PASS=.*|CUBEJS_DB_PASS=changeme_cube_reader|" \
    -e "s|^CUBEJS_API_SECRET=.*|CUBEJS_API_SECRET=${CUBE_SECRET}|" \
    "$CUBE_TEMPLATE" > "$CUBE_ENV"

  echo "  wrote:  $CUBE_ENV"
  echo "           (CUBEJS_DB_* → postgres host + cube_reader role, CUBEJS_API_SECRET aligned with backend)"
fi

echo ""
echo "✅ environment files ready"
