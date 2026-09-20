"""Health plans and their daily tasks (suggestion -> plan -> action -> record)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class HealthPlan(TimestampMixin, Base):
    """A structured, executable health plan owned by one employee."""

    __tablename__ = "health_plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'completed', 'cancelled')",
            name="ck_health_plans_status",
        ),
        Index("ix_health_plans_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    source_agent: Mapped[str] = mapped_column(String(80), nullable=False, default="health_plan_agent")
    source_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class HealthPlanTask(TimestampMixin, Base):
    """One day-level task belonging to a health plan."""

    __tablename__ = "health_plan_tasks"
    __table_args__ = (
        CheckConstraint(
            "completion_status IN ('pending', 'completed', 'skipped')",
            name="ck_health_plan_tasks_status",
        ),
        CheckConstraint(
            "completion_source IN ('manual', 'wearable', 'health_profile', 'mental_checkin')",
            name="ck_health_plan_tasks_source",
        ),
        Index("ix_health_plan_tasks_plan_day", "plan_id", "day_index"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("health_plans.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    task_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_value: Mapped[str | None] = mapped_column(String(60), nullable=True)
    actual_value: Mapped[str | None] = mapped_column(String(60), nullable=True)
    completion_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    completion_source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
