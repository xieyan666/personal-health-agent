"""Mental wellness: daily check-ins and self-assessment records.

Sensitive personal health data.  Every row is scoped by user_id; employees can
only see their own records and admins must never see individual mental data.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class MentalCheckin(TimestampMixin, Base):
    """One employee's mental state check-in for a single day (unique per day)."""

    __tablename__ = "mental_checkins"
    __table_args__ = (
        CheckConstraint("stress_level BETWEEN 1 AND 10", name="ck_mental_checkins_stress"),
        CheckConstraint("energy_level BETWEEN 1 AND 10", name="ck_mental_checkins_energy"),
        Index("ix_mental_checkins_user_date", "user_id", "checkin_date", unique=True),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[str] = mapped_column(String(20), nullable=False, default="一般")
    stress_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    energy_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    sleep_feeling: Mapped[str] = mapped_column(String(20), nullable=False, default="一般")
    stress_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class MentalAssessment(TimestampMixin, Base):
    """A completed self-assessment result (WHO-5 / PSS-10 / GAD-7 / PHQ-9).

    Stored results are screening self-knowledge only and never a diagnosis.
    """

    __tablename__ = "mental_assessments"
    __table_args__ = (
        CheckConstraint(
            "assessment_type IN ('WHO-5', 'PSS-10', 'GAD-7', 'PHQ-9')",
            name="ck_mental_assessments_type",
        ),
        Index("ix_mental_assessments_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Keep the exact definition version used for every completed screening.
    # This prevents future definition changes from altering the meaning of an
    # already persisted result.
    assessment_version: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=True)
    # Keep raw and normalized values separately when a questionnaire needs both.
    raw_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    percentage_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    needs_follow_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # This marker is generated only by explicit, approved safety rules.
    safety_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
