"""Add health services catalog, activities, bookings and benefits."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260826_0013"
down_revision = "20260826_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "health_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("delivery_mode", sa.String(20), nullable=False, server_default="online"),
        sa.Column("suitability", sa.Text(), nullable=True),
        sa.Column("is_annual_check", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_health_services_category", "health_services", ["category"])

    op.create_table(
        "health_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False, server_default="general"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("schedule", sa.String(120), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("participants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "health_activity_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("health_activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_activity_participant_uniq", "health_activity_participants", ["activity_id", "user_id"], unique=True)
    op.create_index("ix_health_activity_participants_user_id", "health_activity_participants", ["user_id"])

    op.create_table(
        "health_service_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("health_services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("booking_time", sa.String(20), nullable=False, server_default="09:00"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')", name="ck_health_service_bookings_status"),
    )
    op.create_index("ix_health_service_bookings_user", "health_service_bookings", ["user_id"])

    op.create_table(
        "employee_health_benefits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benefit_type", sa.String(40), nullable=False),
        sa.Column("benefit_name", sa.String(80), nullable=False),
        sa.Column("annual_quota", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_employee_health_benefits_user_id", "employee_health_benefits", ["user_id"])


def downgrade():
    op.drop_index("ix_employee_health_benefits_user_id", table_name="employee_health_benefits")
    op.drop_table("employee_health_benefits")
    op.drop_index("ix_health_service_bookings_user", table_name="health_service_bookings")
    op.drop_table("health_service_bookings")
    op.drop_index("ix_health_activity_participants_user_id", table_name="health_activity_participants")
    op.drop_index("ix_activity_participant_uniq", table_name="health_activity_participants")
    op.drop_table("health_activity_participants")
    op.drop_table("health_activities")
    op.drop_index("ix_health_services_category", table_name="health_services")
    op.drop_table("health_services")
