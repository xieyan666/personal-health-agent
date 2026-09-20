"""User persistence model."""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """A local or enterprise-authenticated platform user."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "auth_source",
            "external_user_id",
            name="uq_users_auth_source_external_user_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    name_pinyin: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    department_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    position_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("positions.id"), nullable=True)
    company_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="employee", index=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    office_location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    auth_source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_user_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Shanghai"
    )
