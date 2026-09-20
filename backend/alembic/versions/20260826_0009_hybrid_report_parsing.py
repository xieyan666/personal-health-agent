"""Store hybrid parsing metadata and item provenance."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260826_0009"
down_revision = "20260826_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("health_check_reports", sa.Column("parse_mode", sa.String(30), nullable=True))
    op.add_column("health_check_reports", sa.Column("ocr_used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("health_check_reports", sa.Column("parse_warnings", postgresql.JSONB(), nullable=True))
    op.add_column("health_check_reports", sa.Column("parsed_at", sa.DateTime(), nullable=True))
    op.add_column("health_check_indicators", sa.Column("source_type", sa.String(20), nullable=False, server_default="text"))
    op.add_column("health_check_indicators", sa.Column("confidence", sa.Numeric(5, 4), nullable=True))
    op.alter_column("health_check_reports", "ocr_used", server_default=None)
    op.alter_column("health_check_indicators", "source_type", server_default=None)


def downgrade():
    op.drop_column("health_check_indicators", "confidence")
    op.drop_column("health_check_indicators", "source_type")
    op.drop_column("health_check_reports", "parsed_at")
    op.drop_column("health_check_reports", "parse_warnings")
    op.drop_column("health_check_reports", "ocr_used")
    op.drop_column("health_check_reports", "parse_mode")
