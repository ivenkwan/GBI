"""Test data infrastructure — seed SQL and synthetic test data.

Generates realistic synthetic data for development and testing.
Tables: sales, customers, orders, transactions, users, products,
regions, sales_representatives, deals, activity.

Usage:
    uv run python scripts/seed_test_data.py              # seed all tables
    uv run python scripts/seed_test_data.py --tenants 5   # multi-tenant
"""

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging import logger


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
            "status": random.choice(["completed", "completed", "completed", "pending", "failed"]),
        })

    return rows


def generate_users(tenant_id: str, num_rows: int = 200) -> list[dict]:
    """Generate synthetic user records."""
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
            "status": random.choice(["active", "active", "active", "inactive"]),
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
# Table definitions
# ---------------------------------------------------------------------------


TABLE_SCHEMAS = {
    "sales": """
        CREATE TABLE IF NOT EXISTS public.sales (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            region VARCHAR(50) NOT NULL,
            product_id UUID NOT NULL,
            product_name VARCHAR(200) NOT NULL,
            revenue NUMERIC(15, 2) NOT NULL DEFAULT 0,
            units INTEGER NOT NULL DEFAULT 0,
            transaction_date DATE NOT NULL,
            rep_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "customers": """
        CREATE TABLE IF NOT EXISTS public.customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            email VARCHAR(200),
            country VARCHAR(100),
            signup_date DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS public.orders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            customer_id UUID NOT NULL,
            product_id UUID NOT NULL,
            amount NUMERIC(15, 2) NOT NULL,
            order_date DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'completed',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "transactions": """
        CREATE TABLE IF NOT EXISTS public.transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            amount NUMERIC(15, 2) NOT NULL,
            transaction_date DATE NOT NULL,
            type VARCHAR(30) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'completed',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS public.users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            email VARCHAR(200),
            country VARCHAR(100),
            signup_date DATE NOT NULL,
            last_login DATE,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "products": """
        CREATE TABLE IF NOT EXISTS public.products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            product_name VARCHAR(200) NOT NULL,
            category VARCHAR(100) NOT NULL,
            price NUMERIC(15, 2) NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "regions": """
        CREATE TABLE IF NOT EXISTS public.regions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            region_name VARCHAR(100) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "sales_representatives": """
        CREATE TABLE IF NOT EXISTS public.sales_representatives (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            email VARCHAR(200),
            region_id UUID NOT NULL REFERENCES regions(id),
            hire_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "deals": """
        CREATE TABLE IF NOT EXISTS public.deals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            amount NUMERIC(15, 2) NOT NULL,
            rep_id UUID NOT NULL REFERENCES sales_representatives(id),
            region_id UUID NOT NULL REFERENCES regions(id),
            close_date DATE NOT NULL,
            stage VARCHAR(30) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
    "activity": """
        CREATE TABLE IF NOT EXISTS public.activity (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            activity_date DATE NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """,
}


# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------


async def seed_database(
    connection_url: str,
    tenant_id: str = "00000000-0000-0000-0000-000000000001",
    num_tenants: int = 1,
) -> dict:
    """Create tables and seed them with synthetic data."""
    from app.connectors.postgresql_connector import PostgreSQLConnector

    connector = PostgreSQLConnector(connection_url=connection_url)
    stats = {"tables_created": 0, "rows_inserted": 0, "tenants_seeded": 0}

    async with connector:
        # Create tables
        for table_name, ddl in TABLE_SCHEMAS.items():
            try:
                await connector.execute(ddl)
                stats["tables_created"] += 1
                logger.info(f"Created table: {table_name}")
            except Exception as e:
                logger.warning(f"Table {table_name} may already exist: {e}")

        # Seed tenants
        for t in range(num_tenants):
            t_id = tenant_id if t == 0 else str(uuid.uuid4())

            # Generate data
            sales = generate_sales(t_id)
            customers = generate_customers(t_id)
            orders = generate_orders(t_id, customers)
            transactions = generate_transactions(t_id)
            users = generate_users(t_id)
            products = generate_products(t_id)
            regions = generate_regions(t_id)
            reps = generate_sales_reps(t_id, regions)
            deals = generate_deals(t_id, reps, regions)
            activity = generate_activity(t_id, users)

            # Insert in dependency order
            inserts = [
                ("regions", regions),
                ("products", products),
                ("customers", customers),
                ("users", users),
                ("sales_representatives", reps),
                ("deals", deals),
                ("sales", sales),
                ("orders", orders),
                ("transactions", transactions),
                ("activity", activity),
            ]

            for table_name, rows in inserts:
                if not rows:
                    continue

                # Batch insert in chunks of 100
                chunk_size = 100
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i : i + chunk_size]
                    columns = chunk[0].keys()
                    values_placeholder = ", ".join(
                        f"({', '.join(f'${j + 1}' for j in range(len(columns)))})"
                    )

                    # Build parameterized insert
                    sql = f"""
                        INSERT INTO public.{table_name} ({', '.join(columns)})
                        VALUES {values_placeholder}
                        ON CONFLICT (id) DO NOTHING
                    """

                    params = []
                    for row in chunk:
                        params.extend(row.values())

                    await connector.execute(sql, params=params)
                    stats["rows_inserted"] += len(chunk)

                logger.info(f"  Seeded {len(rows)} rows into {table_name}")

            stats["tenants_seeded"] += 1
            logger.info(f"Seeded tenant {t_id}")

    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="Seed test database with synthetic data"
    )
    parser.add_argument(
        "--connection-url",
        default=settings.DATABASE_URL,
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--tenants", type=int, default=1,
        help="Number of tenants to seed (default: 1)",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Drop all tables before seeding",
    )
    args = parser.parse_args()

    if args.clear:
        from app.connectors.postgresql_connector import PostgreSQLConnector
        connector = PostgreSQLConnector(connection_url=args.connection_url)
        async with connector:
            for table_name in TABLE_SCHEMAS:
                try:
                    await connector.execute(f"DROP TABLE IF EXISTS public.{table_name} CASCADE")
                except Exception:
                    pass
            logger.info("Cleared all seed tables")

    stats = await seed_database(
        connection_url=args.connection_url,
        num_tenants=args.tenants,
    )

    print(f"\n{'='*50}")
    print("Test Data Seed Complete")
    print(f"{'='*50}")
    print(f"Tables created:  {stats['tables_created']}")
    print(f"Tenants seeded:  {stats['tenants_seeded']}")
    print(f"Rows inserted:   {stats['rows_inserted']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
