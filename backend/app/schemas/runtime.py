from uuid import UUID

from pydantic import BaseModel, Field


class AgentRuntimeRequest(BaseModel):
    user_id: UUID
    conversation_id: UUID
    content: str = Field(min_length=1)


class AgentRuntimeResponse(BaseModel):
    run_id: UUID
    run_status: str
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    assistant_content: str
