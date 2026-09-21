"""Host-side helpers for the demo CLI — STDLIB ONLY.

This module is imported by ``scripts/demo.py`` on the host, where no
backend dependencies (asyncpg, pydantic-settings, ...) are available.
Anything that needs the app environment belongs in ``ops.py`` and runs
inside the backend container instead.

Conventions:
- Every command goes through :func:`run` so output streams to the user.
- compose is always invoked with the absolute dev-compose file path, so
  the CLI works from any working directory.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# The demo stack layers the demo override on the dev compose file: same
# services, but the frontend serves its production build (see
# docker-compose.demo.yml for why). Plain `make up` uses the dev file alone.
COMPOSE_FILES = [
    REPO_ROOT / "infra" / "docker-compose.dev.yml",
    REPO_ROOT / "infra" / "docker-compose.demo.yml",
]
COMPOSE_ARGS = [arg for f in COMPOSE_FILES for arg in ("-f", str(f))]
BACKEND_ENV = REPO_ROOT / "backend" / ".env"

# The prebuilt pgvector+AGE image CI publishes (skip the slow source build).
GHCR_POSTGRES_IMAGE = "ghcr.io/ivenkwan/gbi/genbi-postgres:latest"
COMPOSE_POSTGRES_IMAGE = "genbi/postgres-pgvector-age:pg16"

BACKEND_HEALTH = "http://localhost:8000/api/v1/health"
BACKEND_READY = "http://localhost:8000/api/v1/health/ready"

# Host-side ports, overridable so the stack coexists with other local
# services (the compose file interpolates the same variables; verify.sh
# reads them too). The backend stays fixed on 8000 — the frontend's
# NEXT_PUBLIC_API_URL and verify.sh both point at it.
PORT_ENV = {
    "pg": ("GENBI_HOST_PG_PORT", 5432),
    "redis": ("GENBI_HOST_REDIS_PORT", 6379),
    "frontend": ("GENBI_HOST_FRONTEND_PORT", 3003),
    "cube": ("GENBI_HOST_CUBE_PORT", 4000),
    "grafana": ("GENBI_HOST_GRAFANA_PORT", 3001),
    "prometheus": ("GENBI_HOST_PROM_PORT", 9090),
}
# Ports remapped this process (reported once, reused by every command).
PORT_CHOICES: dict[str, int] = {}

# container_name → container-side port (docker-compose.dev.yml), used to
# read the running stack's actual published port before bind-testing.
_CONTAINER_PORTS = {
    "pg": ("genbi-postgres", 5432),
    "redis": ("genbi-redis", 6379),
    "frontend": ("genbi-frontend", 3000),
    "cube": ("genbi-cube", 4000),
    "grafana": ("genbi-grafana", 3000),
    "prometheus": ("genbi-prometheus", 9090),
}


def port_choice(service: str) -> int:
    var, default = PORT_ENV[service]
    if var in os.environ:
        with contextlib.suppress(ValueError):
            return int(os.environ[var])
    return PORT_CHOICES.get(service, default)


def frontend_url() -> str:
    return f"http://localhost:{port_choice('frontend')}"


def _port_bindable(port: int) -> bool:
    """True when a docker-proxy-style bind on this port would succeed."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _published_port(service: str) -> int | None:
    """Host port our own running container already publishes, if any."""
    container, container_port = _CONTAINER_PORTS[service]
    result = subprocess.run(
        ["docker", "port", container, str(container_port)],
        capture_output=True,
        text=True,
    )
    for line in (result.stdout or "").splitlines():
        # e.g. "0.0.0.0:6379" or "[::]:6379"
        port_part = line.rsplit(":", 1)[-1]
        with contextlib.suppress(ValueError):
            return int(port_part)
    return None


def configure_ports() -> None:
    """Pick host ports for the stack, avoiding busy ones.

    Precedence: an explicit GENBI_HOST_* env var, then the port our own
    running container already publishes (keeps `compose up` from churning
    containers between CLI invocations), then the default — bumped to the
    next free port when something else on the machine holds it. Candidate
    ports skip every other service's port (an early draft let the frontend
    grab 3001 — grafana's own default — and compose up failed), and choices
    are exported so every compose invocation (and verify.sh) agrees.
    """
    reserved: set[int] = set()
    for service, (var, default) in PORT_ENV.items():
        port = None
        if var in os.environ:
            with contextlib.suppress(ValueError):
                port = int(os.environ[var])
        if port is None:
            port = _published_port(service)
            if port is not None:
                os.environ[var] = str(port)
        reserved.add(port if port is not None else default)

    for service, (var, default) in PORT_ENV.items():
        if var in os.environ:
            continue  # explicit user choice — never second-guess it
        if _port_bindable(default):
            continue
        port = default
        for candidate in range(default + 1, default + 21):
            if candidate not in reserved and _port_bindable(candidate):
                port = candidate
                break
        warn(f"port {default} is busy — {service} will use {port} (pin it by exporting {var})")
        PORT_CHOICES[service] = port
        os.environ[var] = str(port)
        reserved.add(port)


# Keys copied across `demo reset`'s `gen-env.sh --force` regeneration.
# Everything else (JWT secret, Fernet key, Cube secret, DSNs) is refreshed.
PRESERVED_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
)
_PLACEHOLDER_MARKERS = ("REPLACE-ME", "changeme", "change-me")

BOOTSTRAP_TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def step(text: str) -> None:
    print(f"\n{_c('1', '▶ ' + text)}")


def ok(text: str) -> None:
    print(f"  {_c('32', '✅')} {text}")


def warn(text: str) -> None:
    print(f"  {_c('33', '⚠️ ' + text)}")


def err(text: str) -> None:
    print(f"  {_c('31', '❌')} {text}", file=sys.stderr)


def die(text: str, code: int = 1) -> None:
    err(text)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------


def run(cmd: list[str], *, shell: bool = False, check: bool = True, quiet: bool = False):
    """Run a command, streaming output. Returns the CompletedProcess."""
    rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
    if not quiet:
        print(f"  $ {rendered}")
    result = subprocess.run(
        cmd if not shell else rendered,
        shell=shell,
        cwd=REPO_ROOT,
        capture_output=quiet,
        text=True,
    )
    if check and result.returncode != 0:
        output = ""
        if quiet:
            output = (result.stdout or "") + (result.stderr or "")
        die(f"command failed ({result.returncode}): {rendered}\n{output}")
    return result


def compose(*args: str, check: bool = True, quiet: bool = False):
    return run(["docker", "compose", *COMPOSE_ARGS, *args], check=check, quiet=quiet)


def compose_quiet(*args: str) -> subprocess.CompletedProcess:
    """compose with captured output; caller checks returncode."""
    return run(["docker", "compose", *COMPOSE_ARGS, *args], check=False, quiet=True)


def psql(sql: str) -> str:
    """Run SQL in the postgres container; returns stdout ('|'-delimited)."""
    result = subprocess.run(
        [
            "docker",
            "exec",
            "genbi-postgres",
            "psql",
            "-q",
            "-t",
            "-A",
            "-F",
            "|",
            "-U",
            "genbi",
            "-d",
            "genbi",
            "-c",
            sql,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {(result.stderr or '').strip()}")
    return result.stdout.strip()


def docker_available() -> bool:
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------


def http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def backend_ready() -> bool:
    return http_ok(BACKEND_READY)


def wait_until(label: str, fn, timeout_s: int = 180, interval_s: float = 3.0) -> bool:
    """Poll fn() until true or timeout. Prints a waiting notice."""
    deadline = time.monotonic() + timeout_s
    print(f"  … waiting for {label} (up to {timeout_s}s)")
    while time.monotonic() < deadline:
        if fn():
            ok(label)
            return True
        time.sleep(interval_s)
    return False


def compose_services_healthy(*services: str) -> bool:
    """True when every named service reports health=healthy."""
    result = compose_quiet("ps", "--format", "json")
    if result.returncode != 0:
        return False
    seen = {}
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            svc = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = svc.get("Service") or svc.get("Name") or ""
        seen[name] = svc.get("Health") or (svc.get("State") == "running" and "")
    return all(seen.get(s) == "healthy" for s in services)


def ports_match_running() -> bool:
    """True when every running service publishes exactly the chosen port.

    Guards `demo up`'s fast path when the user pins a different port (or the
    default changes) — the stack must be reconciled onto the new mapping,
    not declared "already up".
    """
    for service in PORT_ENV:
        running = _published_port(service)
        if running is not None and running != port_choice(service):
            return False
    return True


def compose_all_services_running() -> bool:
    """True when every service the compose file declares is running.

    Guards `demo up`'s fast path: a partially-started stack (one container
    failed to start) must fall through to the full reconcile flow.
    """
    cfg = compose_quiet("config", "--services")
    if cfg.returncode != 0:
        return False
    expected = {line.strip() for line in (cfg.stdout or "").splitlines() if line.strip()}
    ps = compose_quiet("ps", "--format", "json")
    if ps.returncode != 0:
        return False
    running: set[str] = set()
    for line in (ps.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            svc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if svc.get("State") == "running":
            running.add(svc.get("Service") or svc.get("Name") or "")
    return bool(expected) and expected <= running


def demo_tenants() -> list[dict]:
    """Demo-marked tenants from the marker scan (empty when stack is down)."""
    try:
        raw = psql(
            "SELECT id, name, slug, settings->>'seed', settings->>'seeded_at' "
            "FROM tenants WHERE settings->>'demo' = 'true' ORDER BY created_at"
        )
    except Exception:
        return []
    tenants = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 5:
            continue
        tenants.append(
            {
                "id": parts[0],
                "name": parts[1],
                "slug": parts[2],
                "seed": parts[3],
                "seeded_at": parts[4],
            }
        )
    return tenants


def parse_demo_tenants(raw: str) -> list[dict]:
    """Pure counterpart of demo_tenants() — parse the psql marker output.

    Kept separate from the psql call so the offline test suite can exercise
    the parsing/marker logic without Docker.
    """
    tenants = []
    for line in (raw or "").splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 5:
            continue
        tenants.append(
            {
                "id": parts[0],
                "name": parts[1],
                "slug": parts[2],
                "seed": parts[3],
                "seeded_at": parts[4],
            }
        )
    return tenants


# ---------------------------------------------------------------------------
# .env key preservation (demo reset)
# ---------------------------------------------------------------------------


def _is_real_value(value: str) -> bool:
    v = value.strip()
    if not v:
        return False
    return not any(marker in v for marker in _PLACEHOLDER_MARKERS)


def extract_preserved_keys(env_text: str) -> dict[str, str]:
    """User-supplied API keys worth carrying across a reset.

    A key is preserved only when it is set to something that does not look
    like a gen-env.sh placeholder. Pure function (offline-testable).
    """
    preserved: dict[str, str] = {}
    for line in (env_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in PRESERVED_KEYS and _is_real_value(value):
            preserved[key] = value.strip()
    return preserved


def inject_preserved_keys(env_text: str, keys: dict[str, str]) -> str:
    """Re-apply preserved keys into a freshly generated env text.

    Replaces the existing line when present, appends otherwise. Pure
    function (offline-testable).
    """
    lines = (env_text or "").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in keys:
                out.append(f"{key}={keys[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, value in keys.items():
        if key not in seen:
            out.append(f"{key}={value}")
    return "\n".join(out) + ("\n" if env_text and not env_text.endswith("\n") else "")


def preserve_env_keys() -> dict[str, str]:
    """Read backend/.env and return the keys to survive the reset."""
    if not BACKEND_ENV.is_file():
        return {}
    return extract_preserved_keys(BACKEND_ENV.read_text(encoding="utf-8"))


def restore_env_keys(keys: dict[str, str]) -> None:
    if not keys or not BACKEND_ENV.is_file():
        return
    merged = inject_preserved_keys(BACKEND_ENV.read_text(encoding="utf-8"), keys)
    BACKEND_ENV.write_text(merged, encoding="utf-8")


# ---------------------------------------------------------------------------
# Redis / env inspection
# ---------------------------------------------------------------------------


def purge_redis_tenant_keys(tenant_ids: list[str]) -> int:
    """DEL every genbi:{tenant_id}:* cache key. Returns keys removed."""
    removed = 0
    for tenant_id in tenant_ids:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "genbi-redis",
                "sh",
                "-c",
                f'redis-cli --scan --pattern "genbi:{tenant_id}:*" | xargs -r redis-cli DEL',
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            with contextlib.suppress(ValueError):
                removed += int((result.stdout or "0").strip() or 0)
    return removed


def env_has_real_key(name: str) -> bool:
    if not BACKEND_ENV.is_file():
        return False
    for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return _is_real_value(line.partition("=")[2])
    return False


def _cors_line_has(origin: str) -> bool:
    for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("CORS_ORIGINS=") and origin in stripped:
            return True
    return False


def ensure_cors_origins() -> None:
    """Make sure the backend allows the frontend origin the CLI will use.

    CORS_ORIGINS defaults to the frontend's default port (3003); when the
    port was remapped on a busy machine, the new origin is appended.
    Idempotent; call after env files exist and before the stack starts.
    """
    port = port_choice("frontend")
    origin = f"http://localhost:{port}"
    default_origin = f"http://localhost:{PORT_ENV['frontend'][1]}"
    if not BACKEND_ENV.is_file() or origin == default_origin and _cors_line_has(default_origin):
        return
    lines = BACKEND_ENV.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("CORS_ORIGINS=") and not stripped.startswith("#"):
            if origin in stripped:
                return
            lines[i] = f"{stripped},{origin}"
            BACKEND_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
            warn(f"CORS_ORIGINS extended with {origin} (remapped frontend)")
            return
    lines.append("CORS_ORIGINS=" + ",".join(dict.fromkeys([default_origin, origin])))
    BACKEND_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    warn(f"CORS_ORIGINS set to include {origin} (remapped frontend)")


# ---------------------------------------------------------------------------
# In-container delegation
# ---------------------------------------------------------------------------


def internal_exec(op_args: list[str]) -> None:
    """Run the seed/unseed DB work inside the backend container.

    Mirrors the `make seed` invocation: PYTHONPATH=/app so app.* imports
    resolve, GENBI_DEMO_INTERNAL=1 so demo.py dispatches to ops instead of
    orchestrating compose from the inside.
    """
    env_flag = ["-e", "GENBI_DEMO_INTERNAL=1", "-e", "PYTHONPATH=/app"]
    compose("exec", "-T", *env_flag, "backend", "uv", "run", "python", "scripts/demo.py", *op_args)


def env_marked_internal() -> bool:
    return os.environ.get("GENBI_DEMO_INTERNAL") == "1"
