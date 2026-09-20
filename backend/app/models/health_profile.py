from __future__ import annotations
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base, TimestampMixin

class HealthProfile(TimestampMixin, Base):
    __tablename__ = "health_profiles"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
