"""reports — persisted multi-chart reports.

Revision ID: 0005_reports
Revises: 0004_messages
Create Date: 2026-08-15

Phase 16: the last original-scaffold surface. A report is an LLM-planned
collection of metric sections (Cube query + rendered chart + narrative);
reports + report_sections follow the standard tenant-table recipe (RLS
FORCE + tenant_isolation + genbi_app grants), mirroring 0004_messages.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_reports"
down_revision: str | None = "0004_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            user_id UUID NOT NULL,
            prompt TEXT NOT NULL,
            title VARCHAR(500) NOT NULL,
            summary TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'complete',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_tenant ON public.reports(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON public.reports(user_id)")
    op.execute("ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.reports FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.reports")
    op.execute(
        "CREATE POLICY tenant_isolation ON public.reports "
        "USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.report_sections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            report_id UUID NOT NULL REFERENCES reports(id),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            position INTEGER NOT NULL DEFAULT 0,
            metric_name VARCHAR(255) NOT NULL,
            section_title VARCHAR(500) NOT NULL,
            chart_spec JSONB NOT NULL DEFAULT '{}',
            chart_svg TEXT,
            data_total DOUBLE PRECISION,
            row_count INTEGER NOT NULL DEFAULT 0,
            narrative TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_sections_report ON public.report_sections(report_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_sections_tenant ON public.report_sections(tenant_id)"
    )
    op.execute("ALTER TABLE public.report_sections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.report_sections FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.report_sections")
    op.execute(
        "CREATE POLICY tenant_isolation ON public.report_sections "
        "USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)"
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.reports TO genbi_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.report_sections TO genbi_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.report_sections CASCADE")
    op.execute("DROP TABLE IF EXISTS public.reports CASCADE")
