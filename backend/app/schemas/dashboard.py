"""Read-only contracts for the employee health workspace dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DashboardHealthOverview(BaseModel):
    label: str
    score: int | None = None
    assessed_at: datetime | None = None


class DashboardRiskSummary(BaseModel):
    attention_count: int = 0
    primary_factor: str | None = None
    status: Literal["normal", "attention", "high", "empty"] = "empty"


class DashboardActivePlan(BaseModel):
    id: str | None = None
    name: str | None = None
    current_day: int | None = None
    duration_days: int | None = None
    completion_rate: float | None = None
    status: str = "none"


class DashboardMentalToday(BaseModel):
    checked_in: bool = False
    mood: str | None = None
    stress_level: int | None = None


class DashboardRecommendation(BaseModel):
    id: str
    title: str
    description: str
    source: str
    target_path: str
    tone: Literal["normal", "attention", "info"] = "info"


class DashboardTask(BaseModel):
    id: str
    title: str
    source: str
    target_path: str
    status: Literal["pending", "completed"] = "pending"
    detail: str | None = None


class DashboardActivity(BaseModel):
    id: str
    title: str
    occurred_at: datetime
    target_path: str | None = None
    kind: str = "system"


class DashboardSummaryResponse(BaseModel):
    health_overview: DashboardHealthOverview
    risk_summary: DashboardRiskSummary
    active_plan: DashboardActivePlan
    mental_today: DashboardMentalToday
    recommendations: list[DashboardRecommendation] = Field(default_factory=list)
    today_tasks: list[DashboardTask] = Field(default_factory=list)
    recent_activities: list[DashboardActivity] = Field(default_factory=list)
