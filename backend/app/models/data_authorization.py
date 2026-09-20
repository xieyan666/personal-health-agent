"""Employee data-consent and explicit approval persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class DataConsent(TimestampMixin, Base):
    """A revocable, scope-level authorization granted by one employee."""

    __tablename__ = "data_consents"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_data_consents_status"),
        Index("ix_data_consents_user_scope_status", "user_id", "scope", "status"),
        Index("ix_data_consents_grantee_scope", "grantee_type", "grantee_id", "scope"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    grantee_type: Mapped[str] = mapped_column(String(32), nullable=False)  # agent / service / enterprise
    grantee_id: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentApproval(TimestampMixin, Base):
    """User-confirmed high-risk action approval, initially used by service booking."""

    __tablename__ = "agent_approvals"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'expired')", name="ck_agent_approvals_status"),
        Index("ix_agent_approvals_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    action_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
