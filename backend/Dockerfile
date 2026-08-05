FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies. uv.lock is copied if present (glob); the sync step uses
# --frozen only when the lockfile exists, otherwise resolves from pyproject.
# Once a lockfile is committed, builds are reproducible. Without one (first
# build), uv resolves and writes one — see scripts/setup.sh which runs
# `uv lock` on the host to commit it.
COPY pyproject.toml ./
COPY uv.lock* ./

# shell form so we can branch on lockfile presence
RUN if [ -f uv.lock ]; then \
        uv sync --frozen --no-dev --no-install-project; \
    else \
        uv sync --no-dev --no-install-project; \
    fi

# Copy application
COPY . .

# Install the project itself (same lockfile-presence branch)
RUN if [ -f uv.lock ]; then \
        uv sync --frozen --no-dev; \
    else \
        uv sync --no-dev; \
    fi

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
