"""Add manual-review fields to health_check_indicators for the admin checkup
management workflow (keep original OCR value as the immutable evidence)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "20260831_0021_indicator_review"
down_revision = "20260831_0020_risk_cases"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "health_check_indicators",
        sa.Column("review_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "health_check_indicators",
        sa.Column("reviewed_value", sa.Numeric(12, 3), nullable=True),
    )
    op.add_column(
        "health_check_indicators",
        sa.Column("reviewed_by_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "health_check_indicators",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "health_check_indicators",
        sa.Column("review_note", sa.String(300), nullable=True),
    )


def downgrade():
    op.drop_column("health_check_indicators", "review_note")
    op.drop_column("health_check_indicators", "reviewed_at")
    op.drop_column("health_check_indicators", "reviewed_by_id")
    op.drop_column("health_check_indicators", "reviewed_value")
    op.drop_column("health_check_indicators", "review_status")
