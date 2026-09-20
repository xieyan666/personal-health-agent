"""System monitoring v1: lightweight request metrics and persistent system
alerts.  Agent runs / audit logs / document statuses are reused as-is."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "20260901_0024_system_monitor"
down_revision = "20260901_0023_model_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "request_metrics",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_request_metrics_created", "request_metrics", ["created_at"])
    op.create_index("ix_request_metrics_path", "request_metrics", ["path"])

    op.create_table(
        "system_alerts",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="ERROR"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("trace_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_system_alerts_status", "system_alerts", ["status"])
    op.create_index("ix_system_alerts_created", "system_alerts", ["created_at"])


def downgrade():
    op.drop_table("system_alerts")
    op.drop_table("request_metrics")
