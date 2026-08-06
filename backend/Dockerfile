FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies. uv.lock is copied if present (glob); the sync step uses
# --frozen only when the lockfile exists, otherwise resolves from pyproject.
# Once a lockfile is committed, builds are reproducible. Without one (first
# build), uv resolves and writes one — see scripts/setup.sh which runs
# `uv lock` on the host to commit it.
#
# Build context is the REPO ROOT (set in docker-compose.*.yml) so .claude/
# is in-context; backend sources live under backend/, hence the prefix.
COPY backend/pyproject.toml ./
COPY backend/uv.lock* ./

# shell form so we can branch on lockfile presence
RUN if [ -f uv.lock ]; then \
        uv sync --frozen --no-dev --no-install-project; \
    else \
        uv sync --no-dev --no-install-project; \
    fi

# Copy application (backend sources only)
COPY backend/ ./

# Install the project itself (same lockfile-presence branch)
RUN if [ -f uv.lock ]; then \
        uv sync --frozen --no-dev; \
    else \
        uv sync --no-dev; \
    fi

# Bake the versioned prompt templates into the image. load_prompt() resolves
# /app/.claude/prompts inside the container (the host-relative fallback resolves
# to /.claude/prompts which doesn't exist in the container).
COPY .claude/prompts /app/.claude/prompts

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
