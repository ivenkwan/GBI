#!/usr/bin/env python3
"""GenBI demo environment CLI (Phase 27).

Host-side entry — STDLIB ONLY, so a demo machine needs nothing beyond
docker + python3. Heavy DB work is delegated to ``scripts/demo/ops.py``
running inside the backend container (the ``make seed`` pattern; scripts/
is bind-mounted into the container by the dev compose file).

Commands:
    up       Provision & bring the environment up (idempotent)
    seed     Provision demo data (tenants, users, analytics, content)
    unseed   Remove demo data (platform baseline stays intact)
    reset    Factory reset: volumes, secrets, migrations, verify
    status   Stack health + demo state + credentials

Make aliases: make demo-up | demo-seed | demo-unseed | demo-reset | demo-status
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Make the demo package (and sibling scripts like db_admin) importable no
# matter the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo import common  # noqa: E402
from demo import dataset as demo_dataset  # noqa: E402


def _print_urls() -> None:
    print(
        "\n────────────────────────────────────────────────────────\n"
        " GenBI access URLs:\n"
        f"   Frontend:      {common.frontend_url()}\n"
        "   Backend API:   http://localhost:8000/docs\n"
        "   Health:        http://localhost:8000/api/v1/health\n"
        f"   Cube:          http://localhost:{common.port_choice('cube')}\n"
        f"   Prometheus:    http://localhost:{common.port_choice('prometheus')}\n"
        f"   Grafana:       http://localhost:{common.port_choice('grafana')}   (admin/admin)\n"
        "────────────────────────────────────────────────────────"
    )


def _print_credentials() -> None:
    roster = demo_dataset.build_roster()
    print(f"\nDemo credentials (password for every demo user): {demo_dataset.DEMO_PASSWORD}")
    for entry in roster:
        print(f"\n  {entry['name']}  (slug: {entry['slug']})")
        for user in entry["users"]:
            print(f"    {user['display_role']:<8} {user['email']}")
    print("\nSuggested demo queries:")
    for query in demo_dataset.SUGGESTED_QUERIES:
        print(f"  • {query}")


# ---------------------------------------------------------------------------
# up
# ---------------------------------------------------------------------------


def _alembic_initialized() -> bool:
    """True when the alembic_version table exists and is non-empty."""
    try:
        out = common.psql(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version') "
            "AND EXISTS (SELECT 1 FROM alembic_version)"
        )
    except Exception:
        return False
    return out.strip() == "t"


def _apply_rls_files() -> None:
    rls_dir = common.REPO_ROOT / "infra" / "postgres" / "rls"
    for path in sorted(rls_dir.glob("*.sql")):
        print(f"  $ docker exec -i genbi-postgres psql < {path.name}")
        with path.open("rb") as fh:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    "genbi-postgres",
                    "psql",
                    "-q",
                    "-U",
                    "genbi",
                    "-d",
                    "genbi",
                ],
                stdin=fh,
                capture_output=True,
                text=True,
                cwd=common.REPO_ROOT,
            )
        if result.returncode != 0:
            common.die(f"RLS file failed: {path.name}\n{result.stderr}")


def cmd_up(args) -> int:
    common.step("Prerequisites")
    if not common.docker_available():
        common.die("Docker daemon not reachable — start Docker and re-run.")
    common.ok("docker daemon reachable")

    # Idempotency: a COMPLETE, healthy stack is a no-op. A partial stack
    # (e.g. one container failed mid-bring-up) falls through to the full
    # reconcile flow.
    if (
        common.backend_ready()
        and common.compose_all_services_running()
        and common.ports_match_running()
    ):
        common.ok("stack already up (backend /health/ready green, all services running)")
        _print_urls()
        print("\nNext: make demo-seed to load demo data (or demo-status).")
        return 0

    common.step("Environment files")
    common.run(["bash", str(common.REPO_ROOT / "scripts" / "gen-env.sh")])
    if not common.env_has_real_key("ANTHROPIC_API_KEY"):
        common.warn(
            "ANTHROPIC_API_KEY is not set — LLM chat features will be degraded "
            "(the stack still runs). Add it to backend/.env and restart."
        )
    if not common.env_has_real_key("OPENAI_API_KEY"):
        common.warn("OPENAI_API_KEY is not set — demo seeding will skip embeddings.")
    common.ensure_cors_origins()

    common.step("Images")
    if args.pull:
        common.run(["docker", "pull", common.GHCR_POSTGRES_IMAGE])
        common.run(["docker", "tag", common.GHCR_POSTGRES_IMAGE, common.COMPOSE_POSTGRES_IMAGE])
        common.ok(f"using prebuilt AGE image ({common.COMPOSE_POSTGRES_IMAGE})")
        common.compose("build", "backend", "frontend")
    else:
        common.compose("build")

    common.step("Infrastructure (postgres + redis)")
    common.compose("up", "-d", "postgres", "redis")
    if not common.wait_until(
        "postgres + redis healthy",
        lambda: common.compose_services_healthy("postgres", "redis"),
        timeout_s=120,
    ):
        common.die("postgres/redis did not become healthy — check `make logs`.")

    common.step("Full stack")
    common.compose("up", "-d")
    if not common.wait_until("backend /health/ready", common.backend_ready, timeout_s=240):
        common.die("backend did not become ready — check `docker compose logs backend`.")
    if not common.wait_until(
        "frontend", lambda: common.http_ok(common.frontend_url()), timeout_s=180
    ):
        common.warn(
            "frontend not answering yet — it may still be compiling; retry demo-status shortly."
        )

    common.step("Database migrations")
    if not _alembic_initialized():
        common.compose("exec", "-T", "backend", "uv", "run", "alembic", "stamp", "0001_baseline")
        common.ok("fresh volume stamped at 0001_baseline (init.sql owns the baseline)")
    common.compose("exec", "-T", "backend", "uv", "run", "alembic", "upgrade", "head")
    _apply_rls_files()
    common.ok("migrations + RLS policies applied")

    if not args.no_verify:
        common.step("Verify (scripts/verify.sh)")
        result = common.run(["bash", str(common.REPO_ROOT / "scripts" / "verify.sh")], check=False)
        if result.returncode != 0:
            common.die(
                "verify.sh failed — the stack is up but smoke checks are red "
                "(services may still be settling; retry `make demo-status`)."
            )

    common.ok("demo environment is up")
    _print_urls()
    print("\nNext: make demo-seed to load demo tenants, users, and data.")
    return 0


# ---------------------------------------------------------------------------
# seed / unseed
# ---------------------------------------------------------------------------


def _require_stack() -> None:
    if not common.backend_ready():
        common.die("stack is not up — run `make demo-up` (scripts/demo.py up) first.")


def cmd_seed(args) -> int:
    _require_stack()

    common.step("Seeding demo data (in-container, owner role)")
    internal = [
        "seed",
        "--internal",
        "--tenants",
        str(args.tenants),
        "--seed",
        str(args.seed),
    ]
    if args.random:
        internal.append("--random")
    if args.append:
        internal.append("--append")
    if args.skip_embeddings:
        internal.append("--skip-embeddings")
    common.internal_exec(internal)

    common.step("Redis cache purge")
    demo = common.demo_tenants()
    purged = common.purge_redis_tenant_keys([t["id"] for t in demo])
    common.ok(f"{purged} tenant-scoped cache key(s) removed")

    if args.skip_embeddings or not common.env_has_real_key("OPENAI_API_KEY"):
        common.warn(
            "embeddings were skipped — NL2SQL context retrieval is empty. "
            "Set OPENAI_API_KEY in backend/.env and re-run demo-seed for full fidelity."
        )
    _print_credentials()
    return 0


def cmd_unseed(args) -> int:
    _require_stack()

    demo = common.demo_tenants()
    if not demo:
        print("No demo-marked tenants — nothing to remove.")
        return 0
    tenant_ids = [t["id"] for t in demo]

    common.step(f"Removing {len(demo)} demo tenant(s) (in-container, owner role)")
    common.internal_exec(["unseed", "--internal"])

    common.step("Redis cache purge")
    purged = common.purge_redis_tenant_keys(tenant_ids)
    common.ok(f"{purged} tenant-scoped cache key(s) removed")

    remaining = common.demo_tenants()
    if remaining:
        common.die(f"unseed left {len(remaining)} demo tenant(s) behind — inspect manually.")
    common.ok("demo data removed; platform baseline (bootstrap tenant + admin) intact")
    print(
        "\nNote: audit_log/admin_audit history is retained by design — "
        "`make demo-reset` is the true clean slate."
    )
    return 0


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


def cmd_reset(args) -> int:
    if not args.yes:
        answer = input(
            "This DESTROYS all data (docker volumes) and regenerates secrets.\n"
            "API keys in backend/.env are preserved (use --nuke-env to wipe them).\n"
            "Type 'yes' to continue: "
        )
        if answer.strip().lower() != "yes":
            print("Aborted.")
            return 1

    common.step("Tearing down (docker compose down -v)")
    common.compose("down", "-v")

    common.step("Regenerating environment files")
    preserved = {} if args.nuke_env else common.preserve_env_keys()
    common.run(["bash", str(common.REPO_ROOT / "scripts" / "gen-env.sh"), "--force"])
    if args.nuke_env:
        common.ok("--nuke-env: all previous values discarded")
    elif preserved:
        common.restore_env_keys(preserved)
        common.ok(f"preserved user keys: {', '.join(sorted(preserved))}")
    else:
        common.ok("no user-supplied API keys found to preserve")

    result = cmd_up(args)
    if result == 0:
        print(
            "\nFactory state restored. Fresh-volume credentials (from init.sql):\n"
            "  admin@genbi.local / admin123\n"
            "Next: make demo-seed to load demo data again."
        )
    return result


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def cmd_status(args) -> int:
    common.step("Services")
    common.compose("ps")

    print()
    checks = [
        ("backend liveness", common.http_ok(common.BACKEND_HEALTH)),
        ("backend readiness", common.http_ok(common.BACKEND_READY)),
        ("frontend", common.http_ok(common.frontend_url())),
    ]
    for label, healthy in checks:
        (common.ok if healthy else common.warn)(f"{label}: {'up' if healthy else 'down'}")

    common.step("Demo state")
    demo = common.demo_tenants()
    if demo:
        common.ok(f"seeded: {len(demo)} demo tenant(s)")
        for t in demo:
            print(f"    {t['slug']:<16} {t['name']}  (seed={t['seed']}, at {t['seeded_at']})")
        _print_credentials()
    else:
        common.warn("not seeded (no demo-marked tenants) — run `make demo-seed`")
        print(
            "\nBaseline credentials (fresh-volume bootstrap user):\n  admin@genbi.local / admin123"
        )
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="demo", description="GenBI demo environment lifecycle CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_up = sub.add_parser("up", help="provision & bring the environment up (idempotent)")
    p_up.add_argument(
        "--pull",
        action="store_true",
        help="pull the CI-published pgvector+AGE image instead of building it",
    )
    p_up.add_argument("--no-verify", action="store_true", help="skip scripts/verify.sh")

    p_seed = sub.add_parser("seed", help="provision demo data")
    p_seed.add_argument("--tenants", type=int, default=2)
    p_seed.add_argument("--seed", type=int, default=42)
    p_seed.add_argument(
        "--random", action="store_true", help="non-deterministic data (SystemRandom)"
    )
    p_seed.add_argument(
        "--append", action="store_true", help="keep existing demo tenants instead of replacing them"
    )
    p_seed.add_argument("--skip-embeddings", action="store_true")

    sub.add_parser("unseed", help="remove demo data (baseline stays intact)")

    p_reset = sub.add_parser("reset", help="factory reset to fresh-install defaults")
    p_reset.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p_reset.add_argument(
        "--nuke-env", action="store_true", help="also wipe preserved API keys from backend/.env"
    )
    p_reset.add_argument("--pull", action="store_true")
    p_reset.add_argument("--no-verify", action="store_true")

    sub.add_parser("status", help="stack health + demo state + credentials")
    return parser


def main(argv: list[str]) -> int:
    # In-container mode: the host CLI re-invoked inside the backend container
    # via `docker compose exec -e GENBI_DEMO_INTERNAL=1`.
    if common.env_marked_internal():
        from demo import ops

        return ops.main(argv)

    # Shared-machine friendliness: pick free host ports before anything
    # touches compose (exports GENBI_HOST_* for every subprocess we spawn).
    common.configure_ports()

    args = build_parser().parse_args(argv)
    handlers = {
        "up": cmd_up,
        "seed": cmd_seed,
        "unseed": cmd_unseed,
        "reset": cmd_reset,
        "status": cmd_status,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
