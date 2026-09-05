#!/usr/bin/env bash
# GenBI first-time environment setup.
#
# Checks prerequisites, generates .env files, installs host-side dev deps,
# builds Docker images, starts infra, runs migrations, and verifies the stack.
# Safe to re-run: each step is skipped if its output already exists.
#
# This script does NOT install system packages (Docker, uv, pnpm) — host
# environments differ too much. It checks for them and tells you what's missing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_DEV="docker compose -f infra/docker-compose.dev.yml"

# Color helpers
green() { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
step()  { printf "\n\033[1m▶ %s\033[0m\n" "$1"; }

# --- 1. Prerequisites --------------------------------------------------------
step "Checking prerequisites"

check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "  ✅ $1 ($(command -v "$1"))"
  else
    echo "  ❌ $1 not found"
    return 1
  fi
}

MISSING=0
check_cmd docker    || MISSING=1
check_cmd uv        || MISSING=1
check_cmd pnpm      || MISSING=1
check_cmd node      || MISSING=1
check_cmd python3   || MISSING=1

# Version checks
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -e 'console.log(process.versions.node.split(".")[0])')"
  if [[ "$NODE_MAJOR" -lt 22 ]]; then
    echo "  ⚠️  node $NODE_MAJOR found; GenBI targets Node 22+"
  fi
fi
if command -v python3 >/dev/null 2>&1; then
  PY_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$PY_MINOR" < "3.12" ]]; then
    echo "  ⚠️  python $PY_MINOR found; GenBI targets 3.12+"
  fi
fi

if [[ "$MISSING" -eq 1 ]]; then
  echo ""
  red "Missing prerequisites. Install them, then re-run 'make setup':"
  echo "  • Docker:    https://docs.docker.com/get-docker/"
  echo "  • uv:        curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  • pnpm:      npm install -g pnpm   (needs Node 22+)"
  exit 1
fi

# Docker daemon running?
if ! docker info >/dev/null 2>&1; then
  red "Docker daemon is not running. Start Docker Desktop (or dockerd) and re-run."
  exit 1
fi

# --- 2. Generate .env files --------------------------------------------------
step "Generating environment files"
scripts/gen-env.sh

# --- 3. Host-side dev dependencies -------------------------------------------
step "Installing host-side dev dependencies (for local non-Docker dev)"

if [[ ! -d backend/.venv ]]; then
  (cd backend && uv sync --dev)
  green "  ✅ backend deps installed (backend/.venv)"
else
  echo "  ✅ backend/.venv exists — skipping"
fi

# Generate a committed uv.lock if missing (Docker build wants it)
if [[ ! -f backend/uv.lock ]]; then
  (cd backend && uv lock)
  yellow "  ⚠️  Generated backend/uv.lock — commit it for reproducible builds"
fi

if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && pnpm install)
  green "  ✅ frontend deps installed (frontend/node_modules)"
else
  echo "  ✅ frontend/node_modules exists — skipping"
fi

if [[ ! -f frontend/pnpm-lock.yaml ]]; then
  (cd frontend && pnpm install --lockfile-only 2>/dev/null || pnpm install)
  yellow "  ⚠️  Generated frontend/pnpm-lock.yaml — commit it for reproducible builds"
fi

# --- 4. Build images ---------------------------------------------------------
step "Building Docker images"
$COMPOSE_DEV build
green "  ✅ images built"

# --- 5. Start infra (postgres + redis) and wait healthy ----------------------
step "Starting infrastructure services"
$COMPOSE_DEV up -d postgres redis

echo "  waiting for postgres + redis to be healthy..."
for i in $(seq 1 30); do
  STATUS="$($COMPOSE_DEV ps --format json 2>/dev/null | grep -c '"Health":"healthy"' || true)"
  if [[ "$STATUS" -ge 2 ]]; then break; fi
  sleep 2
done

# --- 6. Apply migrations -----------------------------------------------------
step "Applying database migrations"
# init.sql already created the baseline schema on first boot; alembic stamp
# marks the current revision so future `alembic upgrade head` works.
$COMPOSE_DEV exec -T backend sh -c \
  'uv run alembic current 2>/dev/null | grep -q "0001_baseline" \
   || (uv run alembic stamp 0001_baseline && echo "  stamped at 0001_baseline") \
   || echo "  (alembic not yet available — schema is via init.sql)"' \
  && green "  ✅ migrations current" \
  || yellow "  ⚠️  could not run alembic — schema is via init.sql; check 'make migrate' later"

# --- 7. Bring up the full stack ---------------------------------------------
step "Starting full stack"
$COMPOSE_DEV up -d
echo "  services starting in the background..."

# --- 8. Verify ---------------------------------------------------------------
step "Verifying stack (this waits for services to become healthy)"
sleep 5
if scripts/verify.sh; then
  green ""
  green "🎉 GenBI is up!"
else
  yellow ""
  yellow "⚠️  Some checks failed. The stack may still be starting —"
  echo "        wait 30s and run 'make verify' again."
  echo "        Tail logs with: make logs"
fi

# --- 9. Print access URLs ----------------------------------------------------
cat <<EOF

────────────────────────────────────────────────────────
 GenBI access URLs:
   Frontend:     http://localhost:3000
   Backend API:  http://localhost:8000/docs
   Health:       http://localhost:8000/api/v1/health
   Cube:         http://localhost:4000
   Prometheus:   http://localhost:9090
   Grafana:      http://localhost:3001   (admin/admin)
────────────────────────────────────────────────────────
 Next: set ANTHROPIC_API_KEY in backend/.env to enable LLM features.
 Common commands: make logs | make ps | make verify | make down
EOF
