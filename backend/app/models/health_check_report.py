"""Employee health-check reports and parser-produced structured indicators."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class HealthCheckReport(TimestampMixin, Base):
    """Original report metadata plus a cached, optional AI interpretation."""

    __tablename__ = "health_check_reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    report_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hospital: Mapped[str | None] = mapped_column(String(200), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # This is a private MinIO object key, never a public credential-bearing URL.
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    # A server-produced stage value, not a client-side simulated percentage.
    parse_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parse_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    parse_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    analysis_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analysis_generated_at: Mapped[datetime | None] = mapped_column(nullable=True)


class HealthCheckIndicator(TimestampMixin, Base):
    """A normalised metric emitted by the report parser/import workflow."""

    __tablename__ = "health_check_indicators"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("health_check_reports.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_min: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    reference_max: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    reference_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    flag: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Admin manual-review workflow. The original OCR value stays in ``value`` /
    # ``value_text`` as immutable evidence; ``reviewed_value`` is the corrected one.
    review_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reviewed_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 3), nullable=True)
    reviewed_by_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
