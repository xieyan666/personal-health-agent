"""Extend existing health-check reports for PDF parsing and structured items."""

from alembic import op
import sqlalchemy as sa

revision = "20260826_0007"
down_revision = "20260825_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("health_check_reports", "file_url", new_column_name="object_key")
    op.alter_column("health_check_reports", "status", new_column_name="parse_status")
    op.execute("UPDATE health_check_reports SET parse_status = 'parsed' WHERE parse_status = 'analyzed'")
    op.add_column("health_check_reports", sa.Column("parse_error", sa.Text(), nullable=True))
    op.add_column("health_check_reports", sa.Column("parse_method", sa.String(40), nullable=True))

    op.alter_column("health_check_indicators", "name", new_column_name="item_name")
    op.alter_column("health_check_indicators", "status", new_column_name="flag")
    op.add_column("health_check_indicators", sa.Column("value_text", sa.String(100), nullable=True))
    op.add_column("health_check_indicators", sa.Column("reference_min", sa.Numeric(12, 3), nullable=True))
    op.add_column("health_check_indicators", sa.Column("reference_max", sa.Numeric(12, 3), nullable=True))
    op.alter_column("health_check_indicators", "reference_range", new_column_name="reference_text")
    op.add_column("health_check_indicators", sa.Column("source_page", sa.Integer(), nullable=True))
    op.execute("UPDATE health_check_indicators SET flag = CASE WHEN flag = 'attention' THEN 'high' ELSE flag END")


def downgrade():
    op.execute("UPDATE health_check_indicators SET flag = CASE WHEN flag IN ('high', 'low') THEN 'attention' ELSE flag END")
    op.drop_column("health_check_indicators", "source_page")
    op.alter_column("health_check_indicators", "reference_text", new_column_name="reference_range")
    op.drop_column("health_check_indicators", "reference_max")
    op.drop_column("health_check_indicators", "reference_min")
    op.drop_column("health_check_indicators", "value_text")
    op.alter_column("health_check_indicators", "flag", new_column_name="status")
    op.alter_column("health_check_indicators", "item_name", new_column_name="name")
    op.drop_column("health_check_reports", "parse_method")
    op.drop_column("health_check_reports", "parse_error")
    op.alter_column("health_check_reports", "parse_status", new_column_name="status")
    op.alter_column("health_check_reports", "object_key", new_column_name="file_url")
