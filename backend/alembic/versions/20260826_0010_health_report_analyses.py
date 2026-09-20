"""Persist AI report interpretation results."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260826_0010"
down_revision = "20260826_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "health_report_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("health_check_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(80), nullable=False, server_default="report_analysis_agent"),
        sa.Column("model_name", sa.String(120), nullable=True),
        sa.Column("analysis_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("analysis_result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_health_report_analyses_report_created", "health_report_analyses", ["report_id", "created_at"])
    op.create_index("ix_health_report_analyses_user_id", "health_report_analyses", ["user_id"])
    op.create_index("ix_health_report_analyses_agent_run_id", "health_report_analyses", ["agent_run_id"])


def downgrade():
    op.drop_index("ix_health_report_analyses_agent_run_id", table_name="health_report_analyses")
    op.drop_index("ix_health_report_analyses_user_id", table_name="health_report_analyses")
    op.drop_index("ix_health_report_analyses_report_created", table_name="health_report_analyses")
    op.drop_table("health_report_analyses")
