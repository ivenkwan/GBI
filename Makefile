# GenBI — development task runner.
# Run `make help` for the target list. All targets are idempotent unless noted.

.DEFAULT_GOAL := help
COMPOSE_DEV := docker compose -f infra/docker-compose.dev.yml
COMPOSE_PROD := docker compose -f infra/docker-compose.yml

.PHONY: help setup up down restart logs ps verify secrets migrate seed reset clean deps

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\n"} \
	     /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## First-time setup: check prereqs, gen secrets, install deps, build
	@scripts/setup.sh

up: ## Start the dev stack (detached)
	@$(COMPOSE_DEV) up -d
	@echo "Stack starting. Run 'make verify' once services are healthy."

down: ## Stop the dev stack (keeps volumes/data)
	@$(COMPOSE_DEV) down

restart: ## Restart the dev stack
	@$(COMPOSE_DEV) restart

logs: ## Tail logs for all services (Ctrl-C to exit)
	@$(COMPOSE_DEV) logs -f --tail=100

ps: ## Show service status + health
	@$(COMPOSE_DEV) ps

verify: ## Run smoke checks against the running stack
	@scripts/verify.sh

secrets: ## Regenerate .env files with fresh random secrets
	@scripts/gen-env.sh --force

migrate: ## Apply Alembic migrations inside the backend container
	@$(COMPOSE_DEV) exec -T backend uv run alembic upgrade head

seed: ## Load synthetic test data (requires `make migrate` first — tables come from Alembic 0003)
	@$(COMPOSE_DEV) exec -T -e PYTHONPATH=/app backend uv run python scripts/seed_test_data.py

reset: ## ⚠️ NUKE all data and restart (down -v && up)
	@$(COMPOSE_DEV) down -v
	@$(COMPOSE_DEV) up -d

clean: ## Remove build artifacts, venvs, node_modules, Docker volumes
	@$(COMPOSE_DEV) down -v 2>/dev/null || true
	rm -rf backend/.venv backend/uv.lock frontend/node_modules frontend/.next
	@echo "Cleaned. Run 'make setup' to rebuild."

deps: ## Install host-side dev dependencies (backend uv + frontend pnpm)
	cd backend && uv sync --dev
	cd frontend && pnpm install
