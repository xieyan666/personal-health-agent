"""Conversation API schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ORMResponse


class ConversationCreate(BaseModel):
    user_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    title: Optional[str] = None
    status: str = "active"
    context: Dict[str, Any] = Field(default_factory=dict)
    last_message_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    last_message_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")


class ConversationResponse(ORMResponse):
    id: UUID
    user_id: UUID
    agent_id: UUID
    title: Optional[str]
    status: str
    context: Dict[str, Any]
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
