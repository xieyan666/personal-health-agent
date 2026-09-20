"""Admin risk-case operation contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RiskCaseListItem(BaseModel):
    id: UUID
    risk_assessment_id: UUID
    user_id: UUID
    risk_type: str
    risk_level: str
    source: str | None = None
    department: str | None = None
    status: str
    assigned_plan_id: UUID | None = None
    assigned_service_id: UUID | None = None
    next_review_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    resolved_at: datetime | None = None


class RiskCaseActionOut(BaseModel):
    id: UUID
    actor_user_id: UUID | None = None
    actor_name: str | None = None
    action: str
    note: str | None = None
    created_at: datetime


class RiskCaseDetail(RiskCaseListItem):
    resolution_note: str | None = None
    ignore_reason: str | None = None
    resolved_by_id: UUID | None = None
    ignored_by_id: UUID | None = None
    risk_summary: str | None = None
    actions: list[RiskCaseActionOut] = Field(default_factory=list)


class RiskCaseStats(BaseModel):
    pending: int = 0
    high_priority: int = 0
    processing: int = 0
    closed_this_month: int = 0


class RiskCaseListResponse(BaseModel):
    stats: RiskCaseStats = Field(default_factory=RiskCaseStats)
    items: list[RiskCaseListItem] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)


class StatusUpdateRequest(BaseModel):
    action: str = Field(description="confirm|observe|resolve|ignore")
    note: str | None = Field(default=None, max_length=500)
    ignore_reason: str | None = Field(default=None, max_length=120)
    next_review_days: int | None = Field(default=None, ge=1, le=90)


class LinkPlanRequest(BaseModel):
    plan_id: UUID


class LinkServiceRequest(BaseModel):
    service_id: UUID


class ServiceOption(BaseModel):
    id: UUID
    name: str
    category: str
    description: str | None = None
    delivery_mode: str


class PlanOption(BaseModel):
    id: UUID
    plan_name: str
    plan_type: str
    status: str


class RiskCaseOptions(BaseModel):
    services: list[ServiceOption] = Field(default_factory=list)
    plans: list[PlanOption] = Field(default_factory=list)
