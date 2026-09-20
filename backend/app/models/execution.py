"""Agent execution record model."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class AgentRun(TimestampMixin, Base):
    """A traceable agent run without duplicated full message content."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("prompt_tokens >= 0", name="ck_agent_runs_prompt_tokens"),
        CheckConstraint(
            "completion_tokens >= 0", name="ck_agent_runs_completion_tokens"
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_agent_runs_latency_ms",
        ),
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
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    trigger_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("messages.id"), nullable=True, index=True
    )
    output_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("messages.id"), nullable=True, index=True
    )
    parent_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, default=uuid4, index=True
    )
    model_config_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("model_configs.id"), nullable=True, index=True
    )
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(
        String(80), nullable=True, index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    safety_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship()
    agent: Mapped["Agent"] = relationship()
    conversation: Mapped[Optional["Conversation"]] = relationship()
    trigger_message: Mapped[Optional["Message"]] = relationship(
        foreign_keys=[trigger_message_id]
    )
    output_message: Mapped[Optional["Message"]] = relationship(
        foreign_keys=[output_message_id]
    )
    model_config: Mapped[Optional["ModelConfig"]] = relationship()
    parent_run: Mapped[Optional["AgentRun"]] = relationship(
        remote_side="AgentRun.id",
        back_populates="child_runs",
    )
    child_runs: Mapped[List["AgentRun"]] = relationship(back_populates="parent_run")

