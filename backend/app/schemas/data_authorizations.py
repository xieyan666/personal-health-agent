"""Public contracts for employee data authorization and explicit approvals."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConsentCreate(BaseModel):
    grantee_type: str = Field(pattern="^(agent|service|enterprise)$")
    grantee_id: str = Field(min_length=1, max_length=120)
    scope: str = Field(min_length=3, max_length=120)
    purpose: str = Field(min_length=2, max_length=255)
    expires_at: datetime | None = None


class ConsentUpdate(BaseModel):
    purpose: str | None = Field(default=None, min_length=2, max_length=255)
    expires_at: datetime | None = None


class ConsentResponse(BaseModel):
    id: UUID
    grantee_type: str
    grantee_id: str
    scope: str
    purpose: str
    status: str
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class AccessLogResponse(BaseModel):
    id: UUID
    actor_type: str
    actor_id: str | None
    scope: str | None
    purpose: str | None
    action: str
    outcome: str
    created_at: datetime


class ConsentOverviewResponse(BaseModel):
    active_consent_count: int
    active_scope_count: int
    ai_consent_count: int
    service_consent_count: int
    mental_scope_enabled: bool
    last_access_at: datetime | None
    pending_approval_count: int


class ApprovalCreate(BaseModel):
    action_type: str = Field(default="health_service.booking.create", max_length=80)
    action_payload: dict = Field(default_factory=dict)
    expires_at: datetime | None = None


class ApprovalResponse(BaseModel):
    id: UUID
    action_type: str
    action_payload: dict
    status: str
    requested_at: datetime
    decided_at: datetime | None
    expires_at: datetime | None


class ApprovalDecision(BaseModel):
    decision_note: str | None = Field(default=None, max_length=500)
