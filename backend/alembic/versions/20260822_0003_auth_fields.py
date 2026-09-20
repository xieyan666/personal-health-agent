"""Add authentication profile fields to users."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260822_0003"
down_revision: Union[str, None] = "20260818_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("company_id", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("role", sa.String(32), server_default="employee", nullable=False))
    op.create_index("ix_users_phone", "users", ["phone"])
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_users_role", "users", ["role"])

def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "role")
    op.drop_column("users", "company_id")
    op.drop_column("users", "department")
    op.drop_column("users", "phone")
