"""normalize wearable date column names"""
from alembic import op
revision = "20260825_0002"
down_revision = "20260825_0001"
branch_labels = None
depends_on = None
def upgrade():
    for table in ("sleep_records", "exercise_records", "heart_rate_records"):
        op.alter_column(table, "record_date", new_column_name="date")
def downgrade():
    for table in ("sleep_records", "exercise_records", "heart_rate_records"):
        op.alter_column(table, "date", new_column_name="record_date")
