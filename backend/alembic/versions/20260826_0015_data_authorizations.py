"""Add employee data-consent and approval boundaries.

Revision ID: 20260826_0015
Revises: 20260826_0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260826_0015"
down_revision = "20260826_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantee_type", sa.String(32), nullable=False),
        sa.Column("grantee_id", sa.String(120), nullable=False),
        sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_data_consents_status"),
    )
    op.create_index("ix_data_consents_user_scope_status", "data_consents", ["user_id", "scope", "status"])
    op.create_index("ix_data_consents_grantee_scope", "data_consents", ["grantee_type", "grantee_id", "scope"])

    op.create_table(
        "agent_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("action_payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'expired')", name="ck_agent_approvals_status"),
    )
    op.create_index("ix_agent_approvals_user_status", "agent_approvals", ["user_id", "status"])


def downgrade():
    op.drop_index("ix_agent_approvals_user_status", table_name="agent_approvals")
    op.drop_table("agent_approvals")
    op.drop_index("ix_data_consents_grantee_scope", table_name="data_consents")
    op.drop_index("ix_data_consents_user_scope_status", table_name="data_consents")
    op.drop_table("data_consents")
