"""Tool registry persistence model."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class Tool(TimestampMixin, Base):
    """A registered builtin, HTTP, or MCP tool."""

    __tablename__ = "tools"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(120), unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    implementation_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    input_schema: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    secret_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

