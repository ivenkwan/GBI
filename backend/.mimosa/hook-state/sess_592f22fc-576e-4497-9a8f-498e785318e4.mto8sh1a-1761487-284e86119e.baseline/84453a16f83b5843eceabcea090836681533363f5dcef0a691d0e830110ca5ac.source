"""control plane — platform admins, admin audit, tenant lifecycle columns.

Revision ID: 0008_control_plane
Revises: 0007_report_schedules
Create Date: 2026-09-05

Phase 21 (ADR 009): platform superuser grants, admin-action audit, and the
tenant lifecycle columns (slug / status / settings). Also rebuilds the
tenant FKs as ON DELETE CASCADE so a guarded decommission removes tenant
data with the tenant row, while audit_log keeps its history (its tenant FK
is dropped — audit outlives tenants by design).

RLS policies, the genbi_admin role, and the genbi_auth retirement live in
the paired ``infra/postgres/rls/0008_control_plane_rls.sql``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0008_control_plane"
down_revision: str | None = "0007_report_schedules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables whose tenant FK is rebuilt as ON DELETE CASCADE (decommission).
_CASCADE_TENANT_FK_TABLES = (
    "users",
    "conversations",
    "messages",
    "schema_embeddings",
    "agent_examples",
    "reports",
    "report_sections",
    "dashboards",
    "dashboard_sections",
    "report_schedules",
)


def upgrade() -> None:
    # --- tenant lifecycle columns --------------------------------------
    op.add_column("tenants", sa.Column("slug", sa.String(50), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column("tenants", sa.Column("settings", JSONB(), nullable=True))
    op.create_unique_constraint("uq_tenants_slug", "tenants", ["slug"])
    op.create_check_constraint("ck_tenants_status", "tenants", "status IN ('active', 'suspended')")

    # --- platform admin grants + admin audit ---------------------------
    op.create_table(
        "platform_admins",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("granted_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("revoked_by", UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "admin_audit",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_admin_audit_actor", "admin_audit", ["actor_user_id"])
    op.create_index("idx_admin_audit_created", "admin_audit", ["created_at"])

    # --- tenant FKs → CASCADE (guarded decommission) --------------------
    # Default constraint names from the original CREATE TABLEs
    # (<table>_tenant_id_fkey); rebuilt identically but with CASCADE. The
    # report→sections FK is rebuilt too so section rows follow their report.
    for table in _CASCADE_TENANT_FK_TABLES:
        op.drop_constraint(f"{table}_tenant_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_tenant_id_fkey",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_constraint("report_sections_report_id_fkey", "report_sections", type_="foreignkey")
    op.create_foreign_key(
        "report_sections_report_id_fkey",
        "report_sections",
        "reports",
        ["report_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # audit_log: history outlives the tenant — drop the FK, keep the column.
    op.drop_constraint("audit_log_tenant_id_fkey", "audit_log", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key("audit_log_tenant_id_fkey", "audit_log", "tenants", ["tenant_id"], ["id"])
    op.drop_constraint("report_sections_report_id_fkey", "report_sections", type_="foreignkey")
    op.create_foreign_key(
        "report_sections_report_id_fkey",
        "report_sections",
        "reports",
        ["report_id"],
        ["id"],
    )
    for table in _CASCADE_TENANT_FK_TABLES:
        op.drop_constraint(f"{table}_tenant_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(f"{table}_tenant_id_fkey", table, "tenants", ["tenant_id"], ["id"])
    op.drop_table("admin_audit")
    op.drop_table("platform_admins")
    op.drop_constraint("ck_tenants_status", "tenants", type_="check")
    op.drop_constraint("uq_tenants_slug", "tenants", type_="check")
    op.drop_column("tenants", "settings")
    op.drop_column("tenants", "status")
    op.drop_column("tenants", "slug")
