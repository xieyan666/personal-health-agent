from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision: str = "20260822_0004"
down_revision: Union[str, None] = "20260822_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None
def upgrade() -> None:
    uid = lambda: sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)
    op.create_table("companies", uid(), sa.Column("name", sa.String(160), nullable=False), sa.Column("code", sa.String(80), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_table("employees", uid(), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False), sa.Column("employee_no", sa.String(80), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("department", sa.String(120)), sa.Column("position", sa.String(120)), sa.Column("phone", sa.String(32)), sa.Column("email", sa.String(320)), sa.Column("join_date", sa.Date()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.UniqueConstraint("company_id", "employee_no", name="uq_employees_company_no"))
    op.create_table("roles", uid(), sa.Column("name", sa.String(80), nullable=False, unique=True), sa.Column("description", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_table("permissions", uid(), sa.Column("code", sa.String(100), nullable=False, unique=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.String(255)))
    op.create_table("role_permissions", uid(), sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False), sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id"), nullable=False))
    roles = sa.table("roles", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("name", sa.String), sa.column("description", sa.String))
    perms = sa.table("permissions", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("code", sa.String), sa.column("name", sa.String), sa.column("description", sa.String))
    import uuid
    role_ids = {n: uuid.uuid4() for n in ("employee", "admin", "health_manager")}
    op.bulk_insert(roles, [{"id": i, "name": n, "description": n} for n, i in role_ids.items()])
    codes = [("user:view", "User View"), ("user:create", "User Create"), ("user:update", "User Update"), ("user:delete", "User Delete"), ("report:view", "Report View"), ("report:manage", "Report Manage")]
    perm_ids = {c: uuid.uuid4() for c, _ in codes}
    op.bulk_insert(perms, [{"id": perm_ids[c], "code": c, "name": n} for c, n in codes])
    rp = sa.table("role_permissions", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("role_id", postgresql.UUID(as_uuid=True)), sa.column("permission_id", postgresql.UUID(as_uuid=True)))
    op.bulk_insert(rp, [{"id": uuid.uuid4(), "role_id": role_ids["admin"], "permission_id": perm_ids[c]} for c, _ in codes])
def downgrade() -> None:
    op.drop_table("role_permissions"); op.drop_table("permissions"); op.drop_table("roles"); op.drop_table("employees"); op.drop_table("companies")
