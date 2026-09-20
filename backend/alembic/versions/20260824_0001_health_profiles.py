from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260824_0001"
down_revision = "20260822_0006"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "health_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("height", sa.Numeric(6, 2), nullable=True),
        sa.Column("weight", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_health_profiles_user_id", "health_profiles", ["user_id"])

def downgrade():
    op.drop_index("ix_health_profiles_user_id", table_name="health_profiles")
    op.drop_table("health_profiles")
