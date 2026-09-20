"""User notifications and notification preferences.

Notifications are lightweight, non-sensitive summaries of real business
events (never raw health values).  Preferences gate whether a notification is
created per type; authorization security alerts can bypass the preference.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin

NOTIFICATION_TYPES = (
    "system",
    "health_report",
    "health_risk",
    "health_plan",
    "mental_health",
    "health_service",
    "authorization",
)


class UserNotification(TimestampMixin, Base):
    """A read/unread notification for one employee."""

    __tablename__ = "user_notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('system','health_report','health_risk','health_plan','mental_health','health_service','authorization')",
            name="ck_user_notifications_type",
        ),
        Index("ix_user_notifications_user_read", "user_id", "is_read"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_path: Mapped[str | None] = mapped_column(String(160), nullable=True)


class UserPreference(TimestampMixin, Base):
    """Per-user preferences; only notification_preferences is used in v1."""

    __tablename__ = "user_preferences"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    notification_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
