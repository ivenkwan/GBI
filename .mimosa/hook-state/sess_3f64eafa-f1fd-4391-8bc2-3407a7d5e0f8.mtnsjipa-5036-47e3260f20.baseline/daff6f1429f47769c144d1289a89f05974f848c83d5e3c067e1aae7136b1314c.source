"""analytics seed tables — tenant-scoped demo data with FORCE RLS.

Revision ID: 0003_analytics
Revises: 0002_app_roles
Create Date: 2026-08-15

Creates the 10 synthetic analytics tables used by the demo/seed dataset
(scripts/seed_test_data.py fills them; it no longer performs DDL). Every
table carries tenant_id and gets the same FORCE RLS + tenant_isolation
policy as the metadata tables, so the genbi_app runtime role is tenant-
scoped on analytics queries too — the connector already sets the
`app.current_tenant_id` GUC per transaction.

Note: `web_users` (was `users`) was renamed to stop shadowing the RLS-
enrolled app-login table of the same name in the public schema.

Statements use IF NOT EXISTS / IF EXISTS so this converges on databases
where earlier seed-script DDL already ran. RLS enrollment and teardown use
literal DO blocks with %I identifier quoting (identifiers cannot be bound
as parameters).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_analytics"
down_revision: str | None = "0002_app_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.regions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            region_name VARCHAR(100) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            product_name VARCHAR(200) NOT NULL,
            category VARCHAR(100) NOT NULL,
            price NUMERIC(15, 2) NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.web_users (
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
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.activity (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            activity_date DATE NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # RLS enrollment — same policy shape as the metadata tables (0001/0002).
    # Static table list inside a literal DO block; %I quotes identifiers.
    op.execute(
        """
        DO $$
        DECLARE t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY[
                'regions', 'products', 'customers', 'web_users',
                'sales_representatives', 'deals', 'sales', 'orders',
                'transactions', 'activity'
            ] LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
                EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON public.%I', t);
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON public.%I '
                    'USING (tenant_id = current_setting(''app.current_tenant_id'', true)::UUID)',
                    t
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY[
                'activity', 'transactions', 'orders', 'sales',
                'deals', 'sales_representatives', 'web_users',
                'customers', 'products', 'regions'
            ] LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', t);
            END LOOP;
        END $$;
        """
    )
