"""Add health plans and their daily tasks."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260826_0011"
down_revision = "20260826_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "health_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_name", sa.String(120), nullable=False),
        sa.Column("plan_type", sa.String(40), nullable=False, server_default="general"),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_agent", sa.String(80), nullable=False, server_default="health_plan_agent"),
        sa.Column("source_input", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'paused', 'completed', 'cancelled')", name="ck_health_plans_status"),
    )
    op.create_index("ix_health_plans_user_status", "health_plans", ["user_id", "status"])

    op.create_table(
        "health_plan_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("health_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("task_date", sa.Date(), nullable=True),
        sa.Column("task_type", sa.String(40), nullable=False, server_default="general"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_value", sa.String(60), nullable=True),
        sa.Column("actual_value", sa.String(60), nullable=True),
        sa.Column("completion_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completion_source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("completion_status IN ('pending', 'completed', 'skipped')", name="ck_health_plan_tasks_status"),
        sa.CheckConstraint("completion_source IN ('manual', 'wearable', 'health_profile', 'mental_checkin')", name="ck_health_plan_tasks_source"),
    )
    op.create_index("ix_health_plan_tasks_plan_day", "health_plan_tasks", ["plan_id", "day_index"])
    op.create_index("ix_health_plan_tasks_user_id", "health_plan_tasks", ["user_id"])


def downgrade():
    op.drop_index("ix_health_plan_tasks_user_id", table_name="health_plan_tasks")
    op.drop_index("ix_health_plan_tasks_plan_day", table_name="health_plan_tasks")
    op.drop_table("health_plan_tasks")
    op.drop_index("ix_health_plans_user_status", table_name="health_plans")
    op.drop_table("health_plans")
