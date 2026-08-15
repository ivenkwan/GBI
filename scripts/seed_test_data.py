"""Test data infrastructure — synthetic analytics data for development.

Tables (created by Alembic migration 0003_analytics, all FORCE-RLS tenant-
scoped): sales, customers, orders, transactions, web_users, products,
regions, sales_representatives, deals, activity. This script only INSERTs
data, connecting as the OWNER role (scripts/db_admin.owner_connect) and
setting the tenant GUC per tenant pass (FORCE RLS binds the owner too).

Usage (from the repo root, backend venv active; in-container via `make seed`):
    PYTHONPATH=backend uv run python scripts/seed_test_data.py              # seed all tables
    PYTHONPATH=backend uv run python scripts/seed_test_data.py --tenants 5   # multi-tenant
"""

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta

from app.core.logging import logger
from db_admin import owner_connect, set_tenant_guc


# ---------------------------------------------------------------------------
# Synthetic data generators
# ---------------------------------------------------------------------------

REGIONS = ["North", "South", "East", "West", "Central"]
COUNTRIES = [
    "United States", "Germany", "France", "Japan", "United Kingdom",
    "Canada", "Australia", "Brazil", "India", "Singapore",
]
PRODUCT_CATEGORIES = [
    "Software", "Hardware", "Services", "Support", "Training",
]
PRODUCT_NAMES = [
    "GenBI Enterprise", "GenBI Pro", "GenBI Starter",
    "Data Connector Pack", "Advanced Analytics Add-on",
    "AML Screening Module", "Risk Dashboard Suite",
]
CUSTOMER_NAMES = [
    "Acme Corp", "Globex Inc", "Initech", "Umbrella Co",
    "Stark Industries", "Wayne Enterprises", "Cyberdyne Systems",
    "Weyland-Yutani", "Oscorp", "Aperture Science",
    "Hooli", "Pied Piper", "Massive Dynamic", "Soylent Corp",
    "Dunder Mifflin", "Sterling Cooper", "Los Pollos Hermanos",
    "Oceanic Airlines", "Monarch Sciences", "Buy n Large",
]
SALES_REPS = [
    "Alice Johnson", "Bob Smith", "Carol Williams", "Dave Brown",
    "Eve Davis", "Frank Miller", "Grace Wilson", "Henry Moore",
    "Iris Taylor", "Jack Anderson",
]


def random_date(start: datetime, end: datetime) -> datetime:
    """Generate a random date between start and end."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)


def generate_sales(tenant_id: str, num_rows: int = 500) -> list[dict]:
    """Generate synthetic sales transactions."""
    rows = []
    start = datetime(2024, 1, 1)
    end = datetime(2026, 6, 30)

    for _ in range(num_rows):
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "region": random.choice(REGIONS),
            "product_id": str(uuid.uuid4()),
            "product_name": random.choice(PRODUCT_NAMES),
            "revenue": round(random.uniform(100, 500000), 2),
            "units": random.randint(1, 100),
            "transaction_date": random_date(start, end),
            "rep_id": str(uuid.uuid4()),
        })

    return rows


def generate_customers(tenant_id: str, num_rows: int = 100) -> list[dict]:
    """Generate synthetic customer records."""
    rows = []
    for _ in range(num_rows):
        name = random.choice(CUSTOMER_NAMES)
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": name,
            "email": f"contact@{name.lower().replace(' ', '-')}.com",
            "country": random.choice(COUNTRIES),
            "signup_date": random_date(datetime(2022, 1, 1), datetime(2026, 6, 1)),
            "status": random.choice(["active", "active", "active", "inactive", "churned"]),
        })

    return rows


def generate_orders(tenant_id: str, customers: list[dict], num_rows: int = 1000) -> list[dict]:
    """Generate synthetic orders linked to customers."""
    rows = []
    start = datetime(2024, 1, 1)
    end = datetime(2026, 6, 30)

    for _ in range(num_rows):
        customer = random.choice(customers)
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "customer_id": customer["id"],
            "product_id": str(uuid.uuid4()),
            "amount": round(random.uniform(50, 100000), 2),
            "order_date": random_date(start, end),
            "status": random.choice(["completed", "completed", "completed", "pending", "cancelled"]),
        })

    return rows


def generate_transactions(tenant_id: str, num_rows: int = 2000) -> list[dict]:
    """Generate synthetic financial transactions."""
    rows = []
    start = datetime(2024, 1, 1)
    end = datetime(2026, 6, 30)

    for _ in range(num_rows):
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "amount": round(random.uniform(-10000, 100000), 2),
            "transaction_date": random_date(start, end),
            "type": random.choice(["deposit", "withdrawal", "transfer", "payment"]),
            "status": random.choice(["completed", "completed", "pending", "failed"]),
        })

    return rows


def generate_users(tenant_id: str, num_rows: int = 200) -> list[dict]:
    """Generate synthetic web-user records (analytics data, NOT app logins)."""
    rows = []
    start = datetime(2023, 1, 1)
    end = datetime(2026, 6, 30)

    for _ in range(num_rows):
        signup = random_date(start, end)
        last_login = random_date(signup, min(signup + timedelta(days=180), end))
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": f"User {random.randint(1, 99999)}",
            "email": f"user{random.randint(1, 99999)}@example.com",
            "country": random.choice(COUNTRIES),
            "signup_date": signup,
            "last_login": last_login,
            "status": random.choice(["active", "active", "inactive"]),
        })

    return rows


def generate_products(tenant_id: str) -> list[dict]:
    """Generate product catalog."""
    rows = []
    for name in PRODUCT_NAMES:
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "product_name": name,
            "category": random.choice(PRODUCT_CATEGORIES),
            "price": round(random.uniform(99, 49999), 2),
        })
    return rows


def generate_regions(tenant_id: str) -> list[dict]:
    """Generate region lookup table."""
    return [
        {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "region_name": r}
        for r in REGIONS
    ]


def generate_sales_reps(tenant_id: str, regions: list[dict]) -> list[dict]:
    """Generate sales representative records."""
    rows = []
    for name in SALES_REPS:
        region = random.choice(regions)
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "name": name,
            "region_id": region["id"],
            "email": f"{name.lower().replace(' ', '.')}@company.com",
            "hire_date": random_date(datetime(2020, 1, 1), datetime(2026, 1, 1)),
        })
    return rows


def generate_deals(tenant_id: str, reps: list[dict], regions: list[dict], num_rows: int = 300) -> list[dict]:
    """Generate synthetic deals linked to reps and regions."""
    rows = []
    start = datetime(2024, 1, 1)
    end = datetime(2026, 6, 30)

    for _ in range(num_rows):
        rep = random.choice(reps)
        region = random.choice(regions)
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "amount": round(random.uniform(1000, 1000000), 2),
            "rep_id": rep["id"],
            "region_id": region["id"],
            "close_date": random_date(start, end),
            "stage": random.choice(["prospecting", "negotiation", "closed_won", "closed_lost"]),
        })

    return rows


def generate_activity(tenant_id: str, users: list[dict], num_rows: int = 5000) -> list[dict]:
    """Generate synthetic user activity log."""
    rows = []
    start = datetime(2025, 1, 1)
    end = datetime(2026, 6, 30)

    for _ in range(num_rows):
        user = random.choice(users)
        rows.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "user_id": user["id"],
            "activity_date": random_date(start, end),
            "event_type": random.choice(["login", "query", "export", "dashboard_view", "report_create"]),
        })

    return rows


# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------
# Column-order constants mirror the generator dicts 1:1; inserts go through
# asyncpg executemany with $n positional parameters.

REGION_COLS = ("id", "tenant_id", "region_name")
PRODUCT_COLS = ("id", "tenant_id", "product_name", "category", "price")
CUSTOMER_COLS = ("id", "tenant_id", "name", "email", "country", "signup_date", "status")
WEB_USER_COLS = (
    "id", "tenant_id", "name", "email", "country", "signup_date", "last_login", "status",
)
REP_COLS = ("id", "tenant_id", "name", "region_id", "email", "hire_date")
DEAL_COLS = ("id", "tenant_id", "amount", "rep_id", "region_id", "close_date", "stage")
SALES_COLS = (
    "id", "tenant_id", "region", "product_id", "product_name", "revenue",
    "units", "transaction_date", "rep_id",
)
ORDER_COLS = ("id", "tenant_id", "customer_id", "product_id", "amount", "order_date", "status")
TRANSACTION_COLS = ("id", "tenant_id", "amount", "transaction_date", "type", "status")
ACTIVITY_COLS = ("id", "tenant_id", "user_id", "activity_date", "event_type")


def _tuples(rows: list[dict], cols: tuple[str, ...]) -> list[tuple]:
    """Project generated dicts to value tuples in column order."""
    return [tuple(row[c] for c in cols) for row in rows]


async def _clear_data(conn) -> None:
    """Truncate all analytics tables (RLS does not filter TRUNCATE)."""
    await conn.execute("TRUNCATE TABLE public.activity")
    await conn.execute("TRUNCATE TABLE public.transactions")
    await conn.execute("TRUNCATE TABLE public.orders")
    await conn.execute("TRUNCATE TABLE public.sales")
    await conn.execute("TRUNCATE TABLE public.deals")
    await conn.execute("TRUNCATE TABLE public.sales_representatives")
    await conn.execute("TRUNCATE TABLE public.web_users")
    await conn.execute("TRUNCATE TABLE public.customers")
    await conn.execute("TRUNCATE TABLE public.products")
    await conn.execute("TRUNCATE TABLE public.regions")
    logger.info("Cleared all seed data")


async def _seed_tenant(conn, t_id: str) -> int:
    """Generate and insert one tenant's data. Returns rows inserted."""
    regions = generate_regions(t_id)
    products = generate_products(t_id)
    customers = generate_customers(t_id)
    users = generate_users(t_id)
    reps = generate_sales_reps(t_id, regions)
    deals = generate_deals(t_id, reps, regions)
    sales = generate_sales(t_id)
    orders = generate_orders(t_id, customers)
    transactions = generate_transactions(t_id)
    activity = generate_activity(t_id, users)

    inserted = 0

    # FORCE RLS binds the owner too — the tenant GUC must be set on this
    # connection before any tenant-scoped DML.
    await set_tenant_guc(conn, t_id)

    async with conn.transaction():
        await conn.executemany(
            "INSERT INTO public.regions (id, tenant_id, region_name) "
            "VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
            _tuples(regions, REGION_COLS),
        )
        inserted += len(regions)
        await conn.executemany(
            "INSERT INTO public.products (id, tenant_id, product_name, category, price) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO NOTHING",
            _tuples(products, PRODUCT_COLS),
        )
        inserted += len(products)
        await conn.executemany(
            "INSERT INTO public.customers "
            "(id, tenant_id, name, email, country, signup_date, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
            _tuples(customers, CUSTOMER_COLS),
        )
        inserted += len(customers)
        await conn.executemany(
            "INSERT INTO public.web_users "
            "(id, tenant_id, name, email, country, signup_date, last_login, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING",
            _tuples(users, WEB_USER_COLS),
        )
        inserted += len(users)
        await conn.executemany(
            "INSERT INTO public.sales_representatives "
            "(id, tenant_id, name, region_id, email, hire_date) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING",
            _tuples(reps, REP_COLS),
        )
        inserted += len(reps)
        await conn.executemany(
            "INSERT INTO public.deals "
            "(id, tenant_id, amount, rep_id, region_id, close_date, stage) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
            _tuples(deals, DEAL_COLS),
        )
        inserted += len(deals)

        for i in range(0, len(sales), 500):
            chunk = _tuples(sales[i:i + 500], SALES_COLS)
            await conn.executemany(
                "INSERT INTO public.sales "
                "(id, tenant_id, region, product_id, product_name, revenue, units, "
                "transaction_date, rep_id) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING",
                chunk,
            )
            inserted += len(chunk)
        for i in range(0, len(orders), 500):
            chunk = _tuples(orders[i:i + 500], ORDER_COLS)
            await conn.executemany(
                "INSERT INTO public.orders "
                "(id, tenant_id, customer_id, product_id, amount, order_date, status) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
                chunk,
            )
            inserted += len(chunk)
        for i in range(0, len(transactions), 500):
            chunk = _tuples(transactions[i:i + 500], TRANSACTION_COLS)
            await conn.executemany(
                "INSERT INTO public.transactions "
                "(id, tenant_id, amount, transaction_date, type, status) "
                "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING",
                chunk,
            )
            inserted += len(chunk)
        for i in range(0, len(activity), 500):
            chunk = _tuples(activity[i:i + 500], ACTIVITY_COLS)
            await conn.executemany(
                "INSERT INTO public.activity "
                "(id, tenant_id, user_id, activity_date, event_type) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO NOTHING",
                chunk,
            )
            inserted += len(chunk)

    return inserted


async def seed_database(
    connection_url: str | None,
    tenant_id: str = "00000000-0000-0000-0000-000000000001",
    num_tenants: int = 1,
) -> dict:
    """Insert synthetic data into the (migration-created) analytics tables."""
    stats = {"rows_inserted": 0, "tenants_seeded": 0}

    conn = await owner_connect(connection_url)
    try:
        for t in range(num_tenants):
            t_id = tenant_id if t == 0 else str(uuid.uuid4())
            stats["rows_inserted"] += await _seed_tenant(conn, t_id)
            stats["tenants_seeded"] += 1
            logger.info("Seeded tenant %s", t_id)
    finally:
        await conn.close()

    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="Seed test database with synthetic data"
    )
    parser.add_argument(
        "--connection-url",
        default=None,
        help="Owner PostgreSQL connection URL (default: DATABASE_URL_SYNC)",
    )
    parser.add_argument(
        "--tenants", type=int, default=1,
        help="Number of tenants to seed (default: 1)",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Truncate all seed tables before seeding",
    )
    args = parser.parse_args()

    conn = await owner_connect(args.connection_url)
    try:
        if args.clear:
            await _clear_data(conn)
    finally:
        await conn.close()

    stats = await seed_database(
        connection_url=args.connection_url,
        num_tenants=args.tenants,
    )

    print()
    print("=" * 50)
    print("Test Data Seed Complete")
    print("=" * 50)
    print("Tenants seeded:  " + str(stats["tenants_seeded"]))
    print("Rows inserted:   " + str(stats["rows_inserted"]))
    print()


if __name__ == "__main__":
    asyncio.run(main())
