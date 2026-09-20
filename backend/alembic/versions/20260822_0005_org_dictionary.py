from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
revision = "20260822_0005"
down_revision = "20260822_0004"
branch_labels = None
depends_on = None
DEPTS = {"技术研发部": ["后端开发工程师", "前端开发工程师", "全栈工程师", "架构师", "DevOps工程师"], "人工智能部": ["AI算法工程师", "大模型应用工程师", "AI Agent工程师", "计算机视觉算法工程师", "NLP算法工程师"], "数据平台部": ["数据工程师", "数据分析师", "数据开发工程师"], "产品部": ["产品经理", "高级产品经理"], "测试质量部": ["测试工程师", "自动化测试工程师"], "基础设施部": ["运维工程师", "云计算工程师", "SRE工程师"], "运营部": ["内容运营", "用户运营"], "市场销售部": ["市场经理", "销售经理"], "人力资源部": [], "财务部": [], "管理层": []}
def upgrade():
    op.create_table("departments", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), unique=True, nullable=False), sa.Column("description", sa.String(255)))
    op.create_table("positions", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=False), sa.Column("name", sa.String(120), nullable=False))
    op.add_column("users", sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True)); op.add_column("users", sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_users_department", "users", "departments", ["department_id"], ["id"]); op.create_foreign_key("fk_users_position", "users", "positions", ["position_id"], ["id"])
    ids = {n: uuid.uuid4() for n in DEPTS}; t = sa.table("departments", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("name", sa.String)); op.bulk_insert(t, [{"id": i, "name": n} for n, i in ids.items()])
    p = sa.table("positions", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("department_id", postgresql.UUID(as_uuid=True)), sa.column("name", sa.String)); op.bulk_insert(p, [{"id": uuid.uuid4(), "department_id": ids[d], "name": n} for d, ns in DEPTS.items() for n in ns])
def downgrade():
    op.drop_constraint("fk_users_position", "users", type_="foreignkey"); op.drop_constraint("fk_users_department", "users", type_="foreignkey"); op.drop_column("users", "position_id"); op.drop_column("users", "department_id"); op.drop_table("positions"); op.drop_table("departments")
