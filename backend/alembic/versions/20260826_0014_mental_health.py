"""Add mental wellness check-ins and assessment records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260826_0014"
down_revision = "20260826_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mental_checkins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("mood", sa.String(20), nullable=False, server_default="一般"),
        sa.Column("stress_level", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("energy_level", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("sleep_feeling", sa.String(20), nullable=False, server_default="一般"),
        sa.Column("stress_sources", postgresql.JSONB(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("stress_level BETWEEN 1 AND 10", name="ck_mental_checkins_stress"),
        sa.CheckConstraint("energy_level BETWEEN 1 AND 10", name="ck_mental_checkins_energy"),
    )
    op.create_index("ix_mental_checkins_user_date", "mental_checkins", ["user_id", "checkin_date"], unique=True)

    op.create_table(
        "mental_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_type", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("level", sa.String(20), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("assessment_type IN ('WHO-5', 'PSS-10', 'GAD-7', 'PHQ-9')", name="ck_mental_assessments_type"),
    )
    op.create_index("ix_mental_assessments_user", "mental_assessments", ["user_id"])


def downgrade():
    op.drop_index("ix_mental_assessments_user", table_name="mental_assessments")
    op.drop_table("mental_assessments")
    op.drop_index("ix_mental_checkins_user_date", table_name="mental_checkins")
    op.drop_table("mental_checkins")
