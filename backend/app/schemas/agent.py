"""Agent API schemas."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ORMResponse


class AgentCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    scope: Literal["system", "personal"]
    owner_user_id: Optional[UUID] = None
    category: str
    status: str
    model_config_id: Optional[UUID] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)

    model_config = ConfigDict(extra="forbid")


class AgentUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[Literal["system", "personal"]] = None
    owner_user_id: Optional[UUID] = None
    category: Optional[str] = None
    status: Optional[str] = None
    model_config_id: Optional[UUID] = None
    config: Optional[Dict[str, Any]] = None
    version: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(extra="forbid")


class AgentResponse(ORMResponse):
    id: UUID
    code: str
    name: str
    description: Optional[str]
    scope: str
    owner_user_id: Optional[UUID]
    category: str
    status: str
    model_config_id: Optional[UUID]
    config: Dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
