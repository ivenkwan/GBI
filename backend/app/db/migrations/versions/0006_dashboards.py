"""dashboards — pinned report sections assembled into a board.

Revision ID: 0006_dashboards
Revises: 0005_reports
Create Date: 2026-09-05

Phase 18: a dashboard pins sections of existing reports (chart + metric
together) into a persistent layout. Tables are created with Alembic's
structured ops; the RLS policies and genbi_app grants live in the paired
SQL file ``infra/postgres/rls/0006_dashboards_rls.sql`` (applied by
``make migrate`` right after this migration, and by CI) — the same tenant
recipe as 0005_reports: FORCE RLS + tenant_isolation on the tenant GUC.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_dashboards"
down_revision: str | None = "0005_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dashboards",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("idx_dashboards_tenant", "dashboards", ["tenant_id"])
    op.create_index("idx_dashboards_user", "dashboards", ["user_id"])

    op.create_table(
        "dashboard_sections",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dashboard_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("section_position", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["dashboard_id"], ["dashboards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("idx_dashboard_sections_dashboard", "dashboard_sections", ["dashboard_id"])
    op.create_index("idx_dashboard_sections_tenant", "dashboard_sections", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("dashboard_sections")
    op.drop_table("dashboards")
