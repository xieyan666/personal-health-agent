"""Extend users with personal-center profile fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260827_0019"
down_revision = "20260827_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("job_title", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("office_location", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "bio")
    op.drop_column("users", "office_location")
    op.drop_column("users", "job_title")
