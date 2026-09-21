"""Deterministic demo dataset — pure stdlib, no I/O.

Everything the demo seeds is derived here so that a fixed seed produces a
byte-identical dataset on every run (same rows, same numbers, same chart
data, same narratives). The value pools mirror ``scripts/seed_test_data.py``
(this module cannot import it — that script pulls in app dependencies —
so the small constant lists are duplicated on purpose).

Row shapes match the analytics tables created by Alembic 0003 and the
content tables (wiki 0011, reports 0005, dashboards 0006, conversations
0004). IDs are uuid5-derived from a fixed namespace so cross-table FKs
are stable across runs.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

# Fixed namespace for uuid5-derived demo IDs (never collide with uuid4s).
DEMO_NS = uuid.UUID("a7c1f4e2-5b39-4d6a-9c8e-2f1b0d4a6e55")

DEMO_PASSWORD = "Demo123!"
DEMO_VERSION = 1
DEFAULT_ROW_COUNTS = {
    "sales": 500,
    "customers": 100,
    "orders": 1000,
    "transactions": 2000,
    "web_users": 200,
    "deals": 300,
    "activity": 5000,
}

DEFAULT_TENANTS = (
    {"name": "Acme Analytics", "slug": "demo-acme"},
    {"name": "Globex Retail", "slug": "demo-globex"},
)

# role key → JWT roles claim. "viewer" is a recognized QUERY_ROLES gate role
# (Phase 15): single-table lookups only. The others are standard app roles.
ROLE_USERS = (
    ("admin", ("admin", "user")),
    ("analyst", ("user",)),
    ("viewer", ("viewer",)),
)

SUGGESTED_QUERIES = (
    "Show me revenue by region for 2025",
    "Which product generated the most revenue?",
    "How many orders were completed last quarter?",
    "What is the monthly units trend?",
)

# ---------------------------------------------------------------------------
# Value pools (mirror scripts/seed_test_data.py)
# ---------------------------------------------------------------------------

REGIONS = ["North", "South", "East", "West", "Central"]
COUNTRIES = [
    "United States",
    "Germany",
    "France",
    "Japan",
    "United Kingdom",
    "Canada",
    "Australia",
    "Brazil",
    "India",
    "Singapore",
]
PRODUCT_NAMES = [
    "GenBI Enterprise",
    "GenBI Pro",
    "GenBI Starter",
    "Data Connector Pack",
    "Advanced Analytics Add-on",
    "AML Screening Module",
    "Risk Dashboard Suite",
]
PRODUCT_CATEGORIES = [
    "Software",
    "Hardware",
    "Services",
    "Support",
    "Training",
]
CUSTOMER_NAMES = [
    "Acme Corp",
    "Globex Inc",
    "Initech",
    "Umbrella Co",
    "Stark Industries",
    "Wayne Enterprises",
    "Cyberdyne Systems",
    "Weyland-Yutani",
    "Oscorp",
    "Aperture Science",
    "Hooli",
    "Pied Piper",
    "Massive Dynamic",
    "Soylent Corp",
    "Dunder Mifflin",
    "Sterling Cooper",
    "Los Pollos Hermanos",
    "Oceanic Airlines",
    "Monarch Sciences",
    "Buy n Large",
]
SALES_REPS = [
    "Alice Johnson",
    "Bob Smith",
    "Carol Williams",
    "Dave Brown",
    "Eve Davis",
    "Frank Miller",
    "Grace Wilson",
    "Henry Moore",
    "Iris Taylor",
    "Jack Anderson",
]

# Fixed date windows (same as seed_test_data.py — stable chart axes).
_D_SALES = (datetime(2024, 1, 1), datetime(2026, 6, 30))
_D_CUSTOMERS = (datetime(2022, 1, 1), datetime(2026, 6, 1))
_D_WEBUSERS = (datetime(2023, 1, 1), datetime(2026, 6, 30))
_D_REPS = (datetime(2020, 1, 1), datetime(2026, 1, 1))
_D_ACTIVITY = (datetime(2025, 1, 1), datetime(2026, 6, 30))


def _uid(scope: str) -> str:
    return str(uuid.uuid5(DEMO_NS, scope))


def _rng_for(seed: int, slug: str, random_mode: bool) -> random.Random:
    if random_mode:
        return random.SystemRandom()
    # String seeds hash deterministically across runs and Python versions.
    return random.Random(f"genbi-demo:{seed}:{slug}")


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------


def build_roster(tenant_count: int = 2) -> list[dict]:
    """Demo tenants + their users. Stable IDs regardless of seed value."""
    roster = []
    for i in range(tenant_count):
        if i < len(DEFAULT_TENANTS):
            name = DEFAULT_TENANTS[i]["name"]
            slug = DEFAULT_TENANTS[i]["slug"]
        else:
            name = f"Demo Tenant {i + 1}"
            slug = f"demo-tenant-{i + 1}"
        roster.append(
            {
                "index": i,
                "name": name,
                "slug": slug,
                "tenant_id": _uid(f"tenant:{slug}"),
                "users": [
                    {
                        "user_id": _uid(f"user:{slug}:{role}"),
                        "email": f"{role}@{slug}.test",
                        "display_role": role,
                        "roles": list(roles),
                    }
                    for role, roles in ROLE_USERS
                ],
            }
        )
    return roster


def tenant_settings(seed: int) -> dict:
    """The demo marker stored in tenants.settings (ops adds seeded_at)."""
    return {"demo": True, "seed": seed, "demo_version": DEMO_VERSION}


# ---------------------------------------------------------------------------
# Analytics generators (deterministic variant of seed_test_data.py)
# ---------------------------------------------------------------------------


def _rand_date(rng: random.Random, start: datetime, end: datetime) -> datetime:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def generate_analytics(
    entry: dict, seed: int = 42, random_mode: bool = False
) -> dict[str, list[dict]]:
    """One tenant's deterministic analytics rows for all 10 tables.

    Unlike seed_test_data.py (SystemRandom, loose uuid4 FKs), rows draw from
    a seeded RNG and reference uuid5-stable product/rep/region/customer rows.
    """
    tid = entry["tenant_id"]
    slug = entry["slug"]
    rng = _rng_for(seed, slug, random_mode)
    counts = DEFAULT_ROW_COUNTS

    regions = [
        {"id": _uid(f"{slug}:region:{r}"), "tenant_id": tid, "region_name": r} for r in REGIONS
    ]
    products = [
        {
            "id": _uid(f"{slug}:product:{name}"),
            "tenant_id": tid,
            "product_name": name,
            "category": rng.choice(PRODUCT_CATEGORIES),
            "price": round(rng.uniform(99, 49999), 2),
        }
        for name in PRODUCT_NAMES
    ]
    customers = []
    for i in range(counts["customers"]):
        name = CUSTOMER_NAMES[i % len(CUSTOMER_NAMES)]
        customers.append(
            {
                "id": _uid(f"{slug}:customer:{i}"),
                "tenant_id": tid,
                "name": f"{name} {i + 1:03d}",
                "email": f"contact{i + 1:03d}@{name.lower().replace(' ', '-')}.com",
                "country": rng.choice(COUNTRIES),
                "signup_date": _rand_date(rng, *_D_CUSTOMERS),
                "status": rng.choice(["active", "active", "active", "inactive", "churned"]),
            }
        )
    web_users = []
    for i in range(counts["web_users"]):
        signup = _rand_date(rng, *_D_WEBUSERS)
        last_login = _rand_date(rng, signup, min(signup + timedelta(days=180), _D_WEBUSERS[1]))
        web_users.append(
            {
                "id": _uid(f"{slug}:webuser:{i}"),
                "tenant_id": tid,
                "name": f"User {rng.randint(1, 99999)}",
                "email": f"user{i + 1:04d}@example.com",
                "country": rng.choice(COUNTRIES),
                "signup_date": signup,
                "last_login": last_login,
                "status": rng.choice(["active", "active", "inactive"]),
            }
        )
    reps = []
    for name in SALES_REPS:
        region = rng.choice(regions)
        reps.append(
            {
                "id": _uid(f"{slug}:rep:{name}"),
                "tenant_id": tid,
                "name": name,
                "region_id": region["id"],
                "email": f"{name.lower().replace(' ', '.')}@{slug}.test",
                "hire_date": _rand_date(rng, *_D_REPS),
            }
        )
    deals = []
    for i in range(counts["deals"]):
        rep = rng.choice(reps)
        region = rng.choice(regions)
        deals.append(
            {
                "id": _uid(f"{slug}:deal:{i}"),
                "tenant_id": tid,
                "amount": round(rng.uniform(1000, 1000000), 2),
                "rep_id": rep["id"],
                "region_id": region["id"],
                "close_date": _rand_date(rng, *_D_SALES),
                "stage": rng.choice(["prospecting", "negotiation", "closed_won", "closed_lost"]),
            }
        )
    sales = []
    for i in range(counts["sales"]):
        product = rng.choice(products)
        rep = rng.choice(reps)
        sales.append(
            {
                "id": _uid(f"{slug}:sale:{i}"),
                "tenant_id": tid,
                "region": rng.choice(REGIONS),
                "product_id": product["id"],
                "product_name": product["product_name"],
                "revenue": round(rng.uniform(100, 500000), 2),
                "units": rng.randint(1, 100),
                "transaction_date": _rand_date(rng, *_D_SALES),
                "rep_id": rep["id"],
            }
        )
    orders = []
    for i in range(counts["orders"]):
        customer = rng.choice(customers)
        product = rng.choice(products)
        orders.append(
            {
                "id": _uid(f"{slug}:order:{i}"),
                "tenant_id": tid,
                "customer_id": customer["id"],
                "product_id": product["id"],
                "amount": round(rng.uniform(50, 100000), 2),
                "order_date": _rand_date(rng, *_D_SALES),
                "status": rng.choice(
                    ["completed", "completed", "completed", "pending", "cancelled"]
                ),
            }
        )
    transactions = []
    for i in range(counts["transactions"]):
        transactions.append(
            {
                "id": _uid(f"{slug}:transaction:{i}"),
                "tenant_id": tid,
                "amount": round(rng.uniform(-10000, 100000), 2),
                "transaction_date": _rand_date(rng, *_D_SALES),
                "type": rng.choice(["deposit", "withdrawal", "transfer", "payment"]),
                "status": rng.choice(["completed", "completed", "pending", "failed"]),
            }
        )
    activity = []
    for i in range(counts["activity"]):
        user = rng.choice(web_users)
        activity.append(
            {
                "id": _uid(f"{slug}:activity:{i}"),
                "tenant_id": tid,
                "user_id": user["id"],
                "activity_date": _rand_date(rng, *_D_ACTIVITY),
                "event_type": rng.choice(
                    ["login", "query", "export", "dashboard_view", "report_create"]
                ),
            }
        )

    return {
        "regions": regions,
        "products": products,
        "customers": customers,
        "web_users": web_users,
        "sales_representatives": reps,
        "deals": deals,
        "sales": sales,
        "orders": orders,
        "transactions": transactions,
        "activity": activity,
    }


# Insert column order per table (mirrors seed_test_data.py executemany SQL).
TABLE_COLUMNS = {
    "regions": ("id", "tenant_id", "region_name"),
    "products": ("id", "tenant_id", "product_name", "category", "price"),
    "customers": ("id", "tenant_id", "name", "email", "country", "signup_date", "status"),
    "web_users": (
        "id",
        "tenant_id",
        "name",
        "email",
        "country",
        "signup_date",
        "last_login",
        "status",
    ),
    "sales_representatives": ("id", "tenant_id", "name", "region_id", "email", "hire_date"),
    "deals": ("id", "tenant_id", "amount", "rep_id", "region_id", "close_date", "stage"),
    "sales": (
        "id",
        "tenant_id",
        "region",
        "product_id",
        "product_name",
        "revenue",
        "units",
        "transaction_date",
        "rep_id",
    ),
    "orders": ("id", "tenant_id", "customer_id", "product_id", "amount", "order_date", "status"),
    "transactions": ("id", "tenant_id", "amount", "transaction_date", "type", "status"),
    "activity": ("id", "tenant_id", "user_id", "activity_date", "event_type"),
}


def tuples(rows: list[dict], table: str) -> list[tuple]:
    """Project rows to insert tuples in TABLE_COLUMNS order."""
    cols = TABLE_COLUMNS[table]
    return [tuple(row[c] for c in cols) for row in rows]


# ---------------------------------------------------------------------------
# Content (wiki / report / dashboard / conversation)
# ---------------------------------------------------------------------------


def _chart(chart_type: str, x_field: str, y_field: str, values: list[dict]) -> dict:
    return {
        "chartType": chart_type,
        "encodings": {"x": {"field": x_field}, "y": {"field": y_field}},
        "baseSize": {"width": 600, "height": 400},
        "data": {"values": values},
    }


def _sales_aggregates(sales: list[dict]) -> dict:
    by_region: dict[str, float] = {}
    by_product: dict[str, float] = {}
    by_month: dict[str, int] = {}
    for row in sales:
        by_region[row["region"]] = by_region.get(row["region"], 0.0) + row["revenue"]
        by_product[row["product_name"]] = by_product.get(row["product_name"], 0.0) + row["revenue"]
        month = row["transaction_date"].strftime("%Y-%m")
        by_month[month] = by_month.get(month, 0) + row["units"]
    return {
        "by_region": by_region,
        "by_product": by_product,
        "by_month": by_month,
        "total_revenue": round(sum(r["revenue"] for r in sales), 2),
        "total_units": sum(r["units"] for r in sales),
    }


def build_content(entry: dict, analytics: dict) -> dict:
    """Wiki + report + dashboard + conversation derived from the analytics.

    Chart specs use the same ChartAssemblyInput shape as the reports service
    (``_build_chart_spec``), with values computed from the actual seeded
    rows — the demo numbers in narratives always match the data.
    """
    slug = entry["slug"]
    admin_id = entry["users"][0]["user_id"]
    agg = _sales_aggregates(analytics["sales"])

    region_values = [
        {"region": region, "revenue": round(value, 2)}
        for region, value in sorted(agg["by_region"].items(), key=lambda kv: kv[0])
    ]
    month_values = [
        {"month": month, "units": units} for month, units in sorted(agg["by_month"].items())
    ]
    top_products = sorted(agg["by_product"].items(), key=lambda kv: -kv[1])[:5]
    product_values = [{"product": name, "revenue": round(value, 2)} for name, value in top_products]

    top_region = max(agg["by_region"].items(), key=lambda kv: kv[1])
    best_month = max(agg["by_month"].items(), key=lambda kv: kv[1])
    top_product = top_products[0]

    wiki_pages = [
        {
            "slug": "demo-guide",
            "title": "Getting Started with the Demo",
            "parent_slug": None,
            "content_md": (
                f"# Getting Started with the Demo\n\n"
                f"Welcome to the **{entry['name']}** workspace. This tenant is "
                "part of the GenBI demo environment.\n\n"
                "## Things to try\n\n"
                "1. Open **Chat** and ask a question in plain English.\n"
                "2. Explore **Reports** and pin sections to a dashboard.\n"
                "3. Check **Wiki** pages like the metrics glossary.\n\n"
                "## Example questions\n\n" + "\n".join(f"- {q}" for q in SUGGESTED_QUERIES)
            ),
        },
        {
            "slug": "metrics-glossary",
            "title": "Metrics Glossary",
            "parent_slug": "demo-guide",
            "content_md": (
                "# Metrics Glossary\n\n"
                "| Metric | Definition |\n|---|---|\n"
                "| Revenue | Sum of `sales.revenue` for completed transactions |\n"
                "| Units | Count of `sales.units` sold |\n"
                "| Deal amount | Sum of `deals.amount` regardless of stage |\n"
                "| Active customers | `customers.status = 'active'` |\n\n"
                "Negative `transactions.amount` rows are refunds — they are "
                "expected in the payments data."
            ),
        },
        {
            "slug": "data-caveats",
            "title": "Data Caveats",
            "parent_slug": "demo-guide",
            "content_md": (
                "# Data Caveats\n\n"
                "- Sales span **2024-01 through 2026-06**; partial months at "
                "either edge are not seasonally adjusted.\n"
                "- `deals` includes open pipeline (`prospecting`, "
                "`negotiation`) — filter by stage for won/lost analysis.\n"
                "- `web_users` are product end-users, *not* workspace logins."
            ),
        },
    ]

    report_sections = [
        {
            "position": 1,
            "metric_name": "Sales.revenue",
            "section_title": "Revenue by Region",
            "chart_spec": _chart("Bar Chart", "region", "revenue", region_values),
            "data_total": agg["total_revenue"],
            "row_count": len(region_values),
            "narrative": (
                f"Total revenue across {len(analytics['sales'])} sales rows is "
                f"${agg['total_revenue']:,.2f}. {top_region[0]} leads with "
                f"${top_region[1]:,.2f} "
                f"({top_region[1] / agg['total_revenue']:.0%} of the total)."
            ),
        },
        {
            "position": 2,
            "metric_name": "Sales.units",
            "section_title": "Monthly Units Trend",
            "chart_spec": _chart("Line Chart", "month", "units", month_values),
            "data_total": float(agg["total_units"]),
            "row_count": len(month_values),
            "narrative": (
                f"{agg['total_units']:,} units were sold over "
                f"{len(month_values)} months. The strongest month was "
                f"{best_month[0]} with {best_month[1]:,} units."
            ),
        },
        {
            "position": 3,
            "metric_name": "Sales.revenue",
            "section_title": "Top Products by Revenue",
            "chart_spec": _chart("Bar Chart", "product", "revenue", product_values),
            "data_total": agg["total_revenue"],
            "row_count": len(product_values),
            "narrative": (
                f"{top_product[0]} is the top product with ${top_product[1]:,.2f} in revenue."
            ),
        },
    ]

    conversation_messages = [
        {
            "role": "user",
            "content": "What drove revenue in this workspace?",
            "generated_sql": None,
        },
        {
            "role": "assistant",
            "content": (
                f"Revenue totaled ${agg['total_revenue']:,.2f} across "
                f"{len(analytics['sales'])} sales. {top_region[0]} is the "
                f"strongest region (${top_region[1]:,.2f}), and {top_product[0]} "
                f"is the top product (${top_product[1]:,.2f}). The best month "
                f"by units was {best_month[0]} ({best_month[1]:,} units)."
            ),
            "generated_sql": (
                "SELECT region, SUM(revenue) AS revenue FROM sales "
                "GROUP BY region ORDER BY revenue DESC"
            ),
        },
    ]

    return {
        "wiki_pages": wiki_pages,
        "report": {
            "id": _uid(f"{slug}:report"),
            "title": "Quarterly Revenue Overview",
            "prompt": "Revenue by region, monthly units trend, and top products",
            "summary": (
                f"Executive overview for {entry['name']}: "
                f"${agg['total_revenue']:,.2f} revenue, {agg['total_units']:,} units."
            ),
            "sections": report_sections,
        },
        "dashboard": {
            "id": _uid(f"{slug}:dashboard"),
            "title": f"{entry['name']} — Executive Overview",
            "description": "Pinned sections from the demo report.",
        },
        "conversation": {
            "id": _uid(f"{slug}:conversation"),
            "title": "Revenue deep-dive",
            "user_id": admin_id,
            "messages": conversation_messages,
        },
        "aggregates": agg,
    }


def build_dataset(entry: dict, seed: int = 42, random_mode: bool = False) -> tuple[dict, dict]:
    """Convenience: (analytics, content) for one roster entry."""
    analytics = generate_analytics(entry, seed=seed, random_mode=random_mode)
    return analytics, build_content(entry, analytics)
