"""Extend health_activities and health_activity_participants for the admin
activity-ops workflow (registration window, delivery info, scope, organizer,
participant status for soft-cancel)."""

from alembic import op
import sqlalchemy as sa

revision = "20260831_0022_activity_ops"
down_revision = "20260831_0021_indicator_review"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("health_activities", sa.Column("start_time", sa.String(10), nullable=True))
    op.add_column("health_activities", sa.Column("end_time", sa.String(10), nullable=True))
    op.add_column("health_activities", sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("health_activities", sa.Column("delivery_mode", sa.String(20), nullable=False, server_default="offline"))
    op.add_column("health_activities", sa.Column("location", sa.String(200), nullable=True))
    op.add_column("health_activities", sa.Column("scope", sa.String(20), nullable=False, server_default="all"))
    op.add_column("health_activities", sa.Column("target_department", sa.String(120), nullable=True))
    op.add_column("health_activities", sa.Column("organizer", sa.String(80), nullable=True))
    op.add_column("health_activities", sa.Column("contact_person", sa.String(80), nullable=True))
    op.add_column("health_activity_participants", sa.Column("status", sa.String(20), nullable=False, server_default="joined"))


def downgrade():
    op.drop_column("health_activity_participants", "status")
    op.drop_column("health_activities", "contact_person")
    op.drop_column("health_activities", "organizer")
    op.drop_column("health_activities", "target_department")
    op.drop_column("health_activities", "scope")
    op.drop_column("health_activities", "location")
    op.drop_column("health_activities", "delivery_mode")
    op.drop_column("health_activities", "registration_deadline")
    op.drop_column("health_activities", "end_time")
    op.drop_column("health_activities", "start_time")
