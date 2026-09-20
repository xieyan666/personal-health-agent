"""health wearable records"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20260825_0001"
down_revision = "20260824_0001"
branch_labels = None
depends_on = None
def upgrade():
    for name, cols in {
        "sleep_records": [sa.Column("record_date", sa.Date, nullable=False), sa.Column("sleep_duration", sa.Float, nullable=False), sa.Column("deep_sleep_duration", sa.Float, nullable=False), sa.Column("light_sleep_duration", sa.Float, nullable=False), sa.Column("sleep_quality", sa.String(20), nullable=False), sa.Column("source", sa.String(40), nullable=False, server_default="Wearable")],
        "exercise_records": [sa.Column("record_date", sa.Date, nullable=False), sa.Column("exercise_duration", sa.Integer, nullable=False), sa.Column("steps", sa.Integer, nullable=False), sa.Column("calories", sa.Integer, nullable=False), sa.Column("exercise_type", sa.String(40), nullable=False), sa.Column("source", sa.String(40), nullable=False, server_default="Wearable")],
        "heart_rate_records": [sa.Column("record_date", sa.Date, nullable=False), sa.Column("average_heart_rate", sa.Integer, nullable=False), sa.Column("resting_heart_rate", sa.Integer, nullable=False), sa.Column("max_heart_rate", sa.Integer, nullable=False), sa.Column("source", sa.String(40), nullable=False, server_default="Wearable")],
    }.items():
        op.create_table(name, sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), *cols, sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        op.create_index(f"ix_{name}_user_date", name, ["user_id", "record_date"])
def downgrade():
    for name in ("heart_rate_records", "exercise_records", "sleep_records"):
        op.drop_index(f"ix_{name}_user_date", table_name=name); op.drop_table(name)
