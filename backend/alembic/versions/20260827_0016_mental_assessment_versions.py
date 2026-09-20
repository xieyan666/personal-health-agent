"""Add versioned result metadata to mental self-assessments.

Revision ID: 20260827_0016
Revises: 20260826_0015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260827_0016"
down_revision = "20260826_0015"
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows were created before versioned definitions existed.  Mark
    # them explicitly rather than implying that they used a verified scale.
    op.add_column(
        "mental_assessments",
        sa.Column(
            "assessment_version",
            sa.String(length=64),
            nullable=False,
            server_default="legacy_unversioned",
        ),
    )
    op.add_column("mental_assessments", sa.Column("result_summary", postgresql.JSONB(), nullable=True))
    op.alter_column("mental_assessments", "assessment_version", server_default=None)


def downgrade():
    op.drop_column("mental_assessments", "result_summary")
    op.drop_column("mental_assessments", "assessment_version")
