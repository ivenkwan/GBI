"""In-container demo seed/unseed operations.

Runs INSIDE the backend container (GENBI_DEMO_INTERNAL=1), where the app
dependencies exist. Connects as the owner role via ``db_admin`` and sets
the tenant GUC per tenant pass — the established admin-script pattern
(FORCE RLS binds the owner too).

Layout note: the container mounts ``backend/`` at ``/app``, while host
development keeps the repo shape — the golden-examples path is resolved
by probing both layouts.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from db_admin import owner_connect, set_tenant_guc

from demo import dataset

# Dev bootstrap user + tenant seeded by infra/postgres/init.sql — the audit
# actor for script-driven demo operations (admin_audit has no FK on it) and
# the post-unseed baseline check.
BOOTSTRAP_ADMIN_ID = "00000000-0000-0000-0000-000000000101"
BOOTSTRAP_TENANT_ID = "00000000-0000-0000-0000-000000000001"

_INSERT_CHUNK = 500


def _golden_examples_path() -> str:
    """nl2sql_golden.json under either the container or host repo layout."""
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "tests" / "evals" / "nl2sql_golden.json",  # container: /app
        here.parents[2] / "backend" / "tests" / "evals" / "nl2sql_golden.json",  # host repo
    ):
        if candidate.is_file():
            return str(candidate)
    return str(here.parents[2] / "backend" / "tests" / "evals" / "nl2sql_golden.json")


def _embeddings_configured() -> bool:
    try:
        from app.core.config import settings

        key = (settings.OPENAI_API_KEY or "").strip()
    except Exception:
        return False
    return bool(key) and "REPLACE-ME" not in key and "changeme" not in key.lower()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def find_demo_tenants(conn) -> list[dict]:
    """Every tenant carrying the demo marker in settings."""
    rows = await conn.fetch(
        "SELECT id, name, slug, settings->>'seed' AS seed "
        "FROM tenants WHERE settings->>'demo' = 'true' ORDER BY created_at"
    )
    return [
        {"id": str(r["id"]), "name": r["name"], "slug": r["slug"], "seed": r["seed"]} for r in rows
    ]


# ---------------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------------


async def _audit(conn, action: str, target_id: str, detail: dict) -> None:
    """Best-effort admin_audit row (same shape the tenants service writes)."""
    with contextlib.suppress(Exception):
        await conn.execute(
            "INSERT INTO admin_audit (actor_user_id, action, target_type, target_id, detail) "
            "VALUES ($1::uuid, $2, 'tenant', $3, $4::jsonb)",
            BOOTSTRAP_ADMIN_ID,
            action,
            target_id,
            json.dumps(detail),
        )


async def remove_demo_tenant(conn, row: dict) -> None:
    """Owner-role decommission of one demo tenant.

    Mirrors ``app/services/tenants.decommission_tenant``: analytics rows
    (no tenant FK) are deleted explicitly with the tenant GUC set; the
    tenant delete cascades users/content via the 0008 CASCADE rebuilds;
    audit_log history is retained by design. One literal statement per
    table — table names are never built from variables.
    """
    tenant_id = row["id"]
    await set_tenant_guc(conn, tenant_id)
    # No wrapping transaction: per-table independence — a database without
    # one of the analytics tables must still decommission cleanly.
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM activity")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM transactions")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM orders")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM sales")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM deals")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM web_users")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM customers")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM sales_representatives")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM products")
    with contextlib.suppress(Exception):
        await conn.execute("DELETE FROM regions")
    await conn.execute("DELETE FROM tenants WHERE id = $1::uuid", tenant_id)
    await _audit(
        conn,
        "demo.unseed",
        tenant_id,
        {"name": row["name"], "slug": row["slug"], "source": "demo-cli"},
    )
    print(f"  removed demo tenant {row['slug']} ({row['name']})")


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


# Static INSERT statements, one per table (house rule: no interpolated SQL).
# Column order matches dataset.TABLE_COLUMNS 1:1; values ride $N binds.
_INSERT_SQL = {
    "regions": "INSERT INTO public.regions (id, tenant_id, region_name) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
    "products": "INSERT INTO public.products (id, tenant_id, product_name, category, price) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO NOTHING",
    "customers": "INSERT INTO public.customers (id, tenant_id, name, email, country, signup_date, status) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
    "web_users": "INSERT INTO public.web_users (id, tenant_id, name, email, country, signup_date, last_login, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING",
    "sales_representatives": "INSERT INTO public.sales_representatives (id, tenant_id, name, region_id, email, hire_date) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING",
    "deals": "INSERT INTO public.deals (id, tenant_id, amount, rep_id, region_id, close_date, stage) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
    "sales": "INSERT INTO public.sales (id, tenant_id, region, product_id, product_name, revenue, units, transaction_date, rep_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING",
    "orders": "INSERT INTO public.orders (id, tenant_id, customer_id, product_id, amount, order_date, status) VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
    "transactions": "INSERT INTO public.transactions (id, tenant_id, amount, transaction_date, type, status) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING",
    "activity": "INSERT INTO public.activity (id, tenant_id, user_id, activity_date, event_type) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO NOTHING",
}

# Small tables first (FK sources), then the high-volume tables (chunked).
_INSERT_ORDER = (
    ("regions", False),
    ("products", False),
    ("customers", False),
    ("web_users", False),
    ("sales_representatives", False),
    ("deals", False),
    ("sales", True),
    ("orders", True),
    ("transactions", True),
    ("activity", True),
)


async def _insert_analytics(conn, tenant_id: str, analytics: dict) -> int:
    inserted = 0
    for table, chunked in _INSERT_ORDER:
        rows = dataset.tuples(analytics[table], table)
        sql = _INSERT_SQL[table]
        if not chunked:
            await conn.executemany(sql, rows)
            inserted += len(rows)
            continue
        for i in range(0, len(rows), _INSERT_CHUNK):
            batch = rows[i : i + _INSERT_CHUNK]
            await conn.executemany(sql, batch)
            inserted += len(batch)
    return inserted


async def _insert_content(conn, entry: dict, content: dict) -> None:
    tenant_id = entry["tenant_id"]
    admin_id = entry["users"][0]["user_id"]

    for page in content["wiki_pages"]:
        page_id = await conn.fetchval(
            "INSERT INTO wiki_pages (tenant_id, slug, title, content_md, parent_slug, created_by, updated_by) "
            "VALUES ($1::uuid, $2, $3, $4, $5, $6::uuid, $6::uuid) "
            "ON CONFLICT (tenant_id, slug) DO UPDATE SET "
            "title = EXCLUDED.title, content_md = EXCLUDED.content_md, updated_at = NOW() "
            "RETURNING id",
            tenant_id,
            page["slug"],
            page["title"],
            page["content_md"],
            page["parent_slug"],
            admin_id,
        )
        await conn.execute(
            "INSERT INTO wiki_page_revisions (page_id, tenant_id, version, title, content_md, edited_by) "
            "VALUES ($1::uuid, $2::uuid, 1, $3, $4, $5::uuid)",
            page_id,
            tenant_id,
            page["title"],
            page["content_md"],
            admin_id,
        )

    report = content["report"]
    await conn.execute(
        "INSERT INTO reports (id, tenant_id, user_id, prompt, title, summary, status) "
        "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'complete') "
        "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, summary = EXCLUDED.summary",
        report["id"],
        tenant_id,
        admin_id,
        report["prompt"],
        report["title"],
        report["summary"],
    )
    for section in report["sections"]:
        await conn.execute(
            "INSERT INTO report_sections "
            "(report_id, tenant_id, position, metric_name, section_title, chart_spec, data_total, row_count, narrative) "
            "VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7, $8, $9)",
            report["id"],
            tenant_id,
            section["position"],
            section["metric_name"],
            section["section_title"],
            json.dumps(section["chart_spec"]),
            section["data_total"],
            section["row_count"],
            section["narrative"],
        )

    dashboard = content["dashboard"]
    await conn.execute(
        "INSERT INTO dashboards (id, tenant_id, user_id, title, description) "
        "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5) "
        "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title",
        dashboard["id"],
        tenant_id,
        admin_id,
        dashboard["title"],
        dashboard["description"],
    )
    for section in report["sections"]:
        await conn.execute(
            "INSERT INTO dashboard_sections (dashboard_id, tenant_id, report_id, section_position, position) "
            "VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $4)",
            dashboard["id"],
            tenant_id,
            report["id"],
            section["position"],
        )

    conversation = content["conversation"]
    await conn.execute(
        "INSERT INTO conversations (id, tenant_id, user_id, title) "
        "VALUES ($1::uuid, $2::uuid, $3::uuid, $4) "
        "ON CONFLICT (id) DO NOTHING",
        conversation["id"],
        tenant_id,
        conversation["user_id"],
        conversation["title"],
    )
    for message in conversation["messages"]:
        await conn.execute(
            "INSERT INTO messages (conversation_id, tenant_id, role, content, generated_sql) "
            "VALUES ($1::uuid, $2::uuid, $3, $4, $5)",
            conversation["id"],
            tenant_id,
            message["role"],
            message["content"],
            message["generated_sql"],
        )


async def _seed_tenant(conn, entry: dict, seed: int, random_mode: bool) -> dict:
    from app.core.security import hash_password

    analytics, content = dataset.build_dataset(entry, seed=seed, random_mode=random_mode)
    tenant_id = entry["tenant_id"]
    settings = dataset.tenant_settings(seed)
    settings["seeded_at"] = datetime.now(UTC).isoformat()

    await set_tenant_guc(conn, tenant_id)
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO tenants (id, name, slug, status, settings) "
            "VALUES ($1::uuid, $2, $3, 'active', $4::jsonb)",
            tenant_id,
            entry["name"],
            entry["slug"],
            json.dumps(settings),
        )
        for user in entry["users"]:
            await conn.execute(
                "INSERT INTO users (id, tenant_id, email, hashed_password, roles, status) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, 'active')",
                user["user_id"],
                tenant_id,
                user["email"],
                hash_password(dataset.DEMO_PASSWORD),
                json.dumps(user["roles"]),
            )
        rows = await _insert_analytics(conn, tenant_id, analytics)
        await _insert_content(conn, entry, content)

    await _audit(
        conn,
        "demo.seed",
        tenant_id,
        {"name": entry["name"], "slug": entry["slug"], "seed": seed, "rows": rows},
    )
    return {"rows": rows, "content": content}


async def _seed_embeddings(conn, entries: list[dict]) -> str:
    """Per-tenant schema embeddings + golden few-shot examples (owner GUC)."""
    from embed_schema import sync_examples, sync_schema

    examples_file = _golden_examples_path()
    for entry in entries:
        result = await sync_schema(conn, tenant_id=entry["tenant_id"])
        examples = await sync_examples(conn, examples_file, entry["tenant_id"])
        print(
            f"  embeddings: {entry['slug']} — {result['embeddings_generated']} tables, "
            f"{examples} golden examples"
        )
    return examples_file


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def seed_command(args) -> int:
    roster = dataset.build_roster(args.tenants)
    conn = await owner_connect()
    totals = {"rows": 0, "replaced": 0, "skipped": 0}
    try:
        existing = {row["slug"]: row for row in await find_demo_tenants(conn)}
        for entry in roster:
            if entry["slug"] in existing:
                if args.append:
                    print(f"  skip (append mode): {entry['slug']} already seeded")
                    totals["skipped"] += 1
                    continue
                await remove_demo_tenant(conn, existing[entry["slug"]])
                totals["replaced"] += 1
            result = await _seed_tenant(conn, entry, args.seed, args.random)
            totals["rows"] += result["rows"]
            print(
                f"  seeded {entry['slug']} ({entry['name']}): "
                f"{result['rows']} analytics rows + users/wiki/report/dashboard/conversation"
            )

        if args.skip_embeddings or not _embeddings_configured():
            reason = "skipped by flag" if args.skip_embeddings else "OPENAI_API_KEY not configured"
            print(f"  ⚠️  embeddings skipped ({reason}) — chat context retrieval will be empty")
        else:
            await _seed_embeddings(conn, roster)
    finally:
        await conn.close()

    print(
        f"demo seed complete: {len(roster) - totals['skipped']} tenant(s), "
        f"{totals['rows']} rows, {totals['replaced']} replaced, {totals['skipped']} skipped"
    )
    return 0


async def unseed_command(args) -> int:
    conn = await owner_connect()
    try:
        demo = await find_demo_tenants(conn)
        if not demo:
            print("no demo-marked tenants found — nothing to remove")
            return 0
        for row in demo:
            await remove_demo_tenant(conn, row)

        remaining = await find_demo_tenants(conn)
        baseline = await conn.fetchval(
            "SELECT count(*) FROM tenants WHERE id = $1::uuid", BOOTSTRAP_TENANT_ID
        )
        baseline_admin = await conn.fetchval(
            "SELECT count(*) FROM users WHERE id = $1::uuid", BOOTSTRAP_ADMIN_ID
        )
        print(f"demo unseed complete: removed {len(demo)} tenant(s)")
        print(f"  post-check: demo tenants remaining = {len(remaining)} (expected 0)")
        print(f"  post-check: bootstrap tenant present = {bool(baseline)}")
        print(f"  post-check: bootstrap admin present = {bool(baseline_admin)}")
        if remaining:
            print("  ❌ demo tenants remain after unseed", file=sys.stderr)
            return 1
        if not baseline or not baseline_admin:
            print("  ❌ baseline platform state damaged", file=sys.stderr)
            return 1
        return 0
    finally:
        await conn.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="demo (internal)")
    sub = parser.add_subparsers(dest="op", required=True)

    p_seed = sub.add_parser("seed")
    p_seed.add_argument("--internal", action="store_true", help=argparse.SUPPRESS)
    p_seed.add_argument("--tenants", type=int, default=2)
    p_seed.add_argument("--seed", type=int, default=42)
    p_seed.add_argument("--random", action="store_true")
    p_seed.add_argument("--append", action="store_true")
    p_seed.add_argument("--skip-embeddings", action="store_true")

    p_unseed = sub.add_parser("unseed")
    p_unseed.add_argument("--internal", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    if args.op == "seed":
        return asyncio.run(seed_command(args))
    return asyncio.run(unseed_command(args))
