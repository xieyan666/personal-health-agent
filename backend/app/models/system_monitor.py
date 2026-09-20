"""System monitoring persistence models: lightweight request metrics and
persistent system alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class RequestMetric(Base):
    """One API request, metadata only (no bodies / headers / auth material)."""

    __tablename__ = "request_metrics"
    __table_args__ = (
        Index("ix_request_metrics_created", "created_at"),
        Index("ix_request_metrics_path", "path"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class SystemAlert(Base):
    """A persisted system alert that an operator can acknowledge / resolve."""

    __tablename__ = "system_alerts"
    __table_args__ = (
        Index("ix_system_alerts_status", "status"),
        Index("ix_system_alerts_created", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="ERROR")
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
