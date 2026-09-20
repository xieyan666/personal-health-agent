from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260825_0004'; down_revision='20260825_0003'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('health_summaries',sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('period',sa.String(30),nullable=False),sa.Column('summary_content',postgresql.JSONB,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_health_summaries_user_period','health_summaries',['user_id','period'])
def downgrade():
    op.drop_index('ix_health_summaries_user_period',table_name='health_summaries');op.drop_table('health_summaries')
