"""report_schedules — recurring regeneration of persisted reports.

Revision ID: 0007_report_schedules
Revises: 0006_dashboards
Create Date: 2026-09-05

Phase 19: one schedule per report (frequency hourly/daily/weekly/monthly).
RLS policies and grants live in the paired SQL file
``infra/postgres/rls/0007_report_schedules_rls.sql`` — including the
scheduler policy that lets the owner role (which the background scheduler
uses) read due rows across tenants while genbi_app stays tenant-scoped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_report_schedules"
down_revision: str | None = "0006_dashboards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.CheckConstraint(
            "frequency IN ('hourly', 'daily', 'weekly', 'monthly')",
            name="ck_report_schedules_frequency",
        ),
        sa.UniqueConstraint("report_id", name="uq_report_schedules_report"),
    )
    op.create_index("idx_report_schedules_next_run", "report_schedules", ["next_run_at"])
    op.create_index("idx_report_schedules_tenant", "report_schedules", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("report_schedules")
