"""Model provider API schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import ORMResponse


class ModelProviderCreate(BaseModel):
    name: str
    provider_type: str
    status: str
    endpoint: Optional[str] = None
    secret_ref: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ModelProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    status: Optional[str] = None
    endpoint: Optional[str] = None
    secret_ref: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class ModelProviderResponse(ORMResponse):
    id: UUID
    name: str
    provider_type: str
    status: str
    endpoint: Optional[str]
    secret_ref: Optional[str]
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
