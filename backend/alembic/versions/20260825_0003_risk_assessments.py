from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260825_0003'; down_revision='20260825_0002'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('risk_assessments', sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('risk_type',sa.String(30),nullable=False),sa.Column('level',sa.String(20),nullable=False),sa.Column('description',sa.Text,nullable=False),sa.Column('recommendation',sa.Text,nullable=False),sa.Column('source',sa.String(40),nullable=False,server_default='Wearable'),sa.Column('assessed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_risk_assessments_user_type','risk_assessments',['user_id','risk_type'])
def downgrade():
    op.drop_index('ix_risk_assessments_user_type',table_name='risk_assessments'); op.drop_table('risk_assessments')
