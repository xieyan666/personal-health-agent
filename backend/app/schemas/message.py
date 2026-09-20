"""Message API schemas."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ORMResponse


class MessageCreate(BaseModel):
    conversation_id: UUID
    parent_message_id: Optional[UUID] = None
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    content_data: Dict[str, Any] = Field(default_factory=dict)
    status: str
    source_type: Optional[str] = None
    source_reference: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str
    safety_status: str

    model_config = ConfigDict(extra="forbid")


class MessageResponse(ORMResponse):
    id: UUID
    conversation_id: UUID
    parent_message_id: Optional[UUID]
    role: str
    content: str
    content_data: Dict[str, Any]
    status: str
    source_type: Optional[str]
    source_reference: Dict[str, Any]
    risk_level: str
    safety_status: str
    created_at: datetime
    updated_at: datetime
