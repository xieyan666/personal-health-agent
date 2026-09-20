"""Request/response contracts for employee health plans."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HealthPlanTaskResponse(BaseModel):
    id: UUID
    plan_id: UUID
    day_index: int
    task_date: date | None = None
    task_type: str
    title: str
    description: str | None = None
    target_value: str | None = None
    actual_value: str | None = None
    completion_status: str
    completion_source: str
    completed_at: datetime | None = None


class HealthPlanStats(BaseModel):
    executed_days: int = 0
    total_days: int = 0
    task_completion_rate: float = 0.0
    streak_days: int = 0
    completed_tasks: int = 0
    total_tasks: int = 0


class HealthPlanResponse(BaseModel):
    id: UUID
    plan_name: str
    plan_type: str
    goal: str | None = None
    duration_days: int
    start_date: date
    end_date: date
    status: str
    source_agent: str
    created_at: datetime
    updated_at: datetime
    tasks: list[HealthPlanTaskResponse] = Field(default_factory=list)
    stats: HealthPlanStats | None = None
    current_day: int | None = None


class HealthPlanSummaryResponse(BaseModel):
    id: UUID
    plan_name: str
    plan_type: str
    goal: str | None = None
    duration_days: int
    start_date: date
    end_date: date
    status: str
    source_agent: str
    created_at: datetime
    stats: HealthPlanStats | None = None
