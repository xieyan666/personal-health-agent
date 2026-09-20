from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260825_0005"
down_revision = "20260825_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "health_risk_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("main_factors", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_health_risk_scores_user_period", "health_risk_scores", ["user_id", "period_start", "period_end"])


def downgrade():
    op.drop_index("ix_health_risk_scores_user_period", table_name="health_risk_scores")
    op.drop_table("health_risk_scores")
