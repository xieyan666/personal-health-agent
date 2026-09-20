"""Conversation and independently persisted message models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Conversation(TimestampMixin, Base):
    """A user-owned conversation served by one primary agent."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id"), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    context: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    user: Mapped["User"] = relationship()
    agent: Mapped["Agent"] = relationship()
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        order_by="Message.created_at",
    )


class Message(TimestampMixin, Base):
    """One message in a conversation, stored separately for traceability."""

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_conversation_created_at",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    parent_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("messages.id"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_type: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True, index=True
    )
    source_reference: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    safety_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    parent: Mapped[Optional["Message"]] = relationship(
        remote_side="Message.id",
        back_populates="children",
    )
    children: Mapped[List["Message"]] = relationship(back_populates="parent")

