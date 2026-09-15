"""tenant users — lifecycle columns for per-tenant user management.

Revision ID: 0010_tenant_users
Revises: 0008_control_plane
Create Date: 2026-09-05

Phase 23 (ADR 009 §6): enable/disable (`status`), `last_login_at` stamped
at login, and the per-tenant email uniqueness the service layer enforces
made real as a composite unique constraint (cross-tenant duplicate emails
remain allowed — that's what login's tenant disambiguation is for).

No RLS/policy changes: genbi_admin already has the control-plane policy on
users (0008 rls file) and genbi_app's tenant_isolation policy is unchanged,
so there is no paired rls/*.sql for this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_tenant_users"
down_revision: str | None = "0008_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.create_check_constraint("ck_users_status", "users", "status IN ('active', 'disabled')")
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.drop_column("users", "last_login_at")
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_column("users", "status")
