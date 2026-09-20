"""Add health-check report metadata and structured indicator storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260825_0006"
down_revision = "20260825_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("health_check_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_name", sa.String(200), nullable=False),
        sa.Column("hospital", sa.String(200), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("analysis_content", postgresql.JSONB(), nullable=True),
        sa.Column("analysis_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_check_reports_user_date", "health_check_reports", ["user_id", "report_date"])
    op.create_table("health_check_indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("health_check_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("value", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("reference_range", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_check_indicators_report", "health_check_indicators", ["report_id"])


def downgrade():
    op.drop_index("ix_health_check_indicators_report", table_name="health_check_indicators")
    op.drop_table("health_check_indicators")
    op.drop_index("ix_health_check_reports_user_date", table_name="health_check_reports")
    op.drop_table("health_check_reports")
