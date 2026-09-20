"""AI report interpretation results persisted for cache reuse.

Each row stores one completed (or failed) attempt to interpret a parsed
health-check report.  The frontend reads the latest row instead of invoking
the model again; only an explicit re-analysis or a changed indicator set
creates a new row.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class HealthReportAnalysis(TimestampMixin, Base):
    """One persisted AI interpretation attempt for a parsed health report."""

    __tablename__ = "health_report_analyses"
    __table_args__ = (
        Index("ix_health_report_analyses_report_created", "report_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("health_check_reports.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False, default="report_analysis_agent")
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    analysis_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
