"""Add structured scoring and safety fields to mental assessments.

Revision ID: 20260827_0017
Revises: 20260827_0016
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_0017"
down_revision = "20260827_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mental_assessments", sa.Column("raw_score", sa.Integer(), nullable=True))
    op.add_column("mental_assessments", sa.Column("percentage_score", sa.Integer(), nullable=True))
    op.add_column("mental_assessments", sa.Column("needs_follow_up", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("mental_assessments", sa.Column("safety_flag", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("mental_assessments", sa.Column("safety_reason", sa.String(length=80), nullable=True))
    op.alter_column("mental_assessments", "needs_follow_up", server_default=None)
    op.alter_column("mental_assessments", "safety_flag", server_default=None)


def downgrade() -> None:
    op.drop_column("mental_assessments", "safety_reason")
    op.drop_column("mental_assessments", "safety_flag")
    op.drop_column("mental_assessments", "needs_follow_up")
    op.drop_column("mental_assessments", "percentage_score")
    op.drop_column("mental_assessments", "raw_score")
