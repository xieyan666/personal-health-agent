"""Request/response contracts for health services, activities, bookings and benefits."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HealthServiceResponse(BaseModel):
    id: UUID
    name: str
    category: str
    description: str | None = None
    duration_minutes: int | None = None
    delivery_mode: str
    suitability: str | None = None
    is_annual_check: bool = False


class HealthActivityResponse(BaseModel):
    id: UUID
    name: str
    activity_type: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    schedule: str | None = None
    duration_minutes: int | None = None
    capacity: int | None = None
    participants: int = 0
    remaining: int | None = None
    joined: bool = False


class HealthServiceBookingResponse(BaseModel):
    id: UUID
    service_id: UUID
    service_name: str
    category: str
    booking_date: date
    booking_time: str
    status: str
    provider: str | None = None


class BookingCreate(BaseModel):
    service_id: UUID
    booking_date: date
    booking_time: str = Field(default="09:00", max_length=20)
    approval_id: UUID | None = None


class EmployeeHealthBenefitResponse(BaseModel):
    id: UUID
    benefit_type: str
    benefit_name: str
    annual_quota: int
    used_quota: int
    remaining_quota: int


class RecommendationResponse(BaseModel):
    service: HealthServiceResponse
    reason: str


class ServiceReasonItem(BaseModel):
    service_id: UUID
    reason: str


class ServiceReasonList(BaseModel):
    reasons: list[ServiceReasonItem] = Field(default_factory=list)


class ServiceRecommendationItem(BaseModel):
    service_id: UUID
    service_name: str
    category: str
    priority: int
    reason: str
    sources: list[str] = Field(default_factory=list)
    ai_generated: bool = False


class ServiceRecommendationListResponse(BaseModel):
    recommendations: list[ServiceRecommendationItem] = Field(default_factory=list)
    ai_status: str = "ok"
