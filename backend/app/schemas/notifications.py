"""Request/response contracts for notifications and preferences."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    content: str
    is_read: bool
    target_path: str | None = None
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationPreferencesResponse(BaseModel):
    system: bool = True
    agent_error: bool = True
    health_report: bool = True
    health_risk: bool = True
    health_plan: bool = True
    mental_health: bool = True
    health_service: bool = True
    authorization: bool = True


class NotificationPreferencesUpdate(BaseModel):
    system: bool | None = None
    agent_error: bool | None = None
    health_report: bool | None = None
    health_risk: bool | None = None
    health_plan: bool | None = None
    mental_health: bool | None = None
    health_service: bool | None = None
    authorization: bool | None = None

    @property
    def as_dict(self) -> dict[str, bool]:
        return {key: value for key, value in self.model_dump().items() if value is not None}
