"""Add admin model-management fields: per-type default flag and embedding
vector dimension on model_configs."""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0023_model_admin"
down_revision = "20260831_0022_activity_ops"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("model_configs", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("model_configs", sa.Column("vector_dimension", sa.Integer(), nullable=True))
    op.create_index("ix_model_configs_type_default", "model_configs", ["model_type", "is_default"])


def downgrade():
    op.drop_index("ix_model_configs_type_default", table_name="model_configs")
    op.drop_column("model_configs", "vector_dimension")
    op.drop_column("model_configs", "is_default")
