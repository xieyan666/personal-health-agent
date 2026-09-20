"""Agent definition persistence model."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Agent(TimestampMixin, Base):
    """A system or user-owned business agent definition."""

    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('system', 'personal')",
            name="ck_agents_scope",
        ),
        CheckConstraint(
            "scope = 'system' OR owner_user_id IS NOT NULL",
            name="ck_agents_personal_owner_required",
        ),
        CheckConstraint("version >= 1", name="ck_agents_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    owner_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    model_config_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("model_configs.id"), nullable=True, index=True
    )
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    owner: Mapped[Optional["User"]] = relationship()
    model_config: Mapped[Optional["ModelConfig"]] = relationship()

