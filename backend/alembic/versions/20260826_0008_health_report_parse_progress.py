"""Add server-side parse progress for uploaded health reports."""

from alembic import op
import sqlalchemy as sa

revision = "20260826_0008"
down_revision = "20260826_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("health_check_reports", sa.Column("parse_progress", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE health_check_reports SET parse_progress = 100 WHERE parse_status IN ('parsed', 'failed')")
    op.alter_column("health_check_reports", "parse_progress", server_default=None)


def downgrade():
    op.drop_column("health_check_reports", "parse_progress")
