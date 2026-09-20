"""Create risk_cases and risk_case_actions for admin risk operations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "20260831_0020_risk_cases"
down_revision = "20260827_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "risk_cases",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "risk_assessment_id", PGUUID(as_uuid=True),
            sa.ForeignKey("risk_assessments.id", ondelete="CASCADE"), nullable=False, unique=True,
        ),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("risk_type", sa.String(30), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("source", sa.String(40), nullable=True),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending",
            index=True,
        ),
        sa.Column("assigned_plan_id", PGUUID(as_uuid=True), sa.ForeignKey("health_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_service_id", PGUUID(as_uuid=True), sa.ForeignKey("health_services.id", ondelete="SET NULL"), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("ignore_reason", sa.String(120), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ignored_by_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_risk_cases_status_updated", "risk_cases", ["status", "updated_at"])

    op.create_table(
        "risk_case_actions",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("risk_case_id", PGUUID(as_uuid=True), sa.ForeignKey("risk_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("actor_user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("risk_case_actions")
    op.drop_index("ix_risk_cases_status_updated", table_name="risk_cases")
    op.drop_table("risk_cases")
