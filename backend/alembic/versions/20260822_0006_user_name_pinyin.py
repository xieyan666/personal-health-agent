from alembic import op
import sqlalchemy as sa
from backend.app.utils.pinyin import name_pinyin

revision = "20260822_0006"
down_revision = "20260822_0005"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("name_pinyin", sa.String(255), nullable=True))
    op.create_index("ix_users_name_pinyin", "users", ["name_pinyin"])
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, display_name FROM users")).mappings()
    for row in rows:
        connection.execute(sa.text("UPDATE users SET name_pinyin=:pinyin WHERE id=:id"), {"id": row["id"], "pinyin": name_pinyin(row["display_name"])})

def downgrade():
    op.drop_index("ix_users_name_pinyin", table_name="users")
    op.drop_column("users", "name_pinyin")
