"""Health services: service catalog, enterprise activities, bookings, benefits.

Employee-facing health resources: examinations, professional consults,
nutrition, exercise and courses, plus enterprise activities and annual
benefit quotas.  All rows are scoped by JWT user_id where personal.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class HealthService(TimestampMixin, Base):
    """A catalog entry of a bookable health service."""

    __tablename__ = "health_services"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="online")
    suitability: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_annual_check: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HealthActivity(TimestampMixin, Base):
    """An enterprise wellness activity (lecture, exercise, course...).

    Status lifecycle (managed by the admin operation layer):
      draft -> registration_open -> registration_closed -> ongoing -> finished
      any state (except finished) may be cancelled by an admin.
    """

    __tablename__ = "health_activities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lecture")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="offline")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    target_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    organizer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(80), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participants: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")


class HealthActivityParticipant(TimestampMixin, Base):
    """Tracks which employee joined which activity (prevents duplicates).

    Cancel does not delete the row; ``status`` flips to ``cancelled`` so the
    registration history is preserved and the unique (activity_id, user_id)
    index remains authoritative.
    """

    __tablename__ = "health_activity_participants"
    __table_args__ = (Index("ix_activity_participant_uniq", "activity_id", "user_id", unique=True),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("health_activities.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="joined")


class HealthServiceBooking(TimestampMixin, Base):
    """A user's booking of a health service."""

    __tablename__ = "health_service_bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled')",
            name="ck_health_service_bookings_status",
        ),
        Index("ix_health_service_bookings_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    service_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("health_services.id", ondelete="CASCADE"), nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    booking_time: Mapped[str] = mapped_column(String(20), nullable=False, default="09:00")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)


class EmployeeHealthBenefit(TimestampMixin, Base):
    """Annual benefit quota for an employee (annual check, consults...)."""

    __tablename__ = "employee_health_benefits"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    benefit_type: Mapped[str] = mapped_column(String(40), nullable=False)
    benefit_name: Mapped[str] = mapped_column(String(80), nullable=False)
    annual_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
