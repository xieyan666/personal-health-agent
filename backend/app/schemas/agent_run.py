"""AgentRun API schemas."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ORMResponse


RunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class AgentRunCreate(BaseModel):
    user_id: UUID
    agent_id: UUID
    conversation_id: UUID
    trigger_message_id: Optional[UUID] = None
    parent_run_id: Optional[UUID] = None
    model_config_id: Optional[UUID] = None
    status: RunStatus
    input_summary: Optional[str] = None
    risk_level: str
    safety_status: str

    model_config = ConfigDict(extra="forbid")


class AgentRunUpdate(BaseModel):
    status: Optional[RunStatus] = None
    output_message_id: Optional[UUID] = None
    output_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    risk_level: Optional[str] = None
    safety_status: Optional[str] = None
    prompt_tokens: Optional[int] = Field(default=None, ge=0)
    completion_tokens: Optional[int] = Field(default=None, ge=0)
    latency_ms: Optional[int] = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class AgentRunResponse(ORMResponse):
    id: UUID
    user_id: UUID
    agent_id: UUID
    conversation_id: Optional[UUID]
    trigger_message_id: Optional[UUID]
    output_message_id: Optional[UUID]
    parent_run_id: Optional[UUID]
    status: str
    trace_id: UUID
    model_config_id: Optional[UUID]
    input_summary: Optional[str]
    output_summary: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    risk_level: str
    safety_status: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: Optional[int]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
