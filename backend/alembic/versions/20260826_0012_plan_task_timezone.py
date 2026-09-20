"""Make task completed_at timezone-aware."""

from alembic import op
import sqlalchemy as sa

revision = "20260826_0012"
down_revision = "20260826_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("health_plan_tasks", "completed_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime(), existing_nullable=True)


def downgrade():
    op.alter_column("health_plan_tasks", "completed_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True), existing_nullable=True)
