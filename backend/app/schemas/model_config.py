"""Model configuration API schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ORMResponse


class ModelConfigCreate(BaseModel):
    provider_id: UUID
    name: str
    model_name: str
    model_type: str
    status: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ModelConfigUpdate(BaseModel):
    provider_id: Optional[UUID] = None
    name: Optional[str] = None
    model_name: Optional[str] = None
    model_type: Optional[str] = None
    status: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class ModelConfigResponse(ORMResponse):
    id: UUID
    provider_id: UUID
    name: str
    model_name: str
    model_type: str
    status: str
    parameters: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
