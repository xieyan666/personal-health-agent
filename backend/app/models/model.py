"""Model provider and callable model configuration persistence models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class ModelProvider(TimestampMixin, Base):
    """A model provider whose credentials are referenced, never stored plainly."""

    __tablename__ = "model_providers"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(80), unique=True)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    endpoint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    secret_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    model_configs: Mapped[List["ModelConfig"]] = relationship(
        back_populates="provider"
    )


class ModelConfig(TimestampMixin, Base):
    """A callable model configuration instance."""

    __tablename__ = "model_configs"
    __table_args__ = (Index("ix_model_configs_type_default", "model_type", "is_default"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_providers.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), unique=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vector_dimension: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    provider: Mapped[ModelProvider] = relationship(back_populates="model_configs")

