"""Admin health-analytics aggregation contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyticsOverview(BaseModel):
    total_employees: int = 0
    covered_employees: int = 0
    coverage_rate: float = 0.0
    attention_employees: int = 0
    attention_rate: float = 0.0
    abnormal_exam_employees: int = 0
    plan_participants: int = 0
    plan_participation_rate: float = 0.0


class HealthDistributionItem(BaseModel):
    level: str
    label: str
    count: int
    percent: float


class RiskRankingItem(BaseModel):
    risk_type: str
    label: str
    count: int
    percent: float


class DepartmentStat(BaseModel):
    department: str
    total: int = 0
    coverage_rate: float = 0.0
    healthy_rate: float = 0.0
    attention_count: int = 0
    attention_rate: float = 0.0
    top_risk: str | None = None
    sample_too_small: bool = False


class TrendPoint(BaseModel):
    period: str
    label: str
    value: float = 0.0
    evaluated: int = 0


class HealthAnalyticsSummary(BaseModel):
    period: str
    department: str | None = None
    overview: AnalyticsOverview = Field(default_factory=AnalyticsOverview)
    health_distribution: list[HealthDistributionItem] = Field(default_factory=list)
    risk_ranking: list[RiskRankingItem] = Field(default_factory=list)
    department_stats: list[DepartmentStat] = Field(default_factory=list)
    risk_trend: list[TrendPoint] = Field(default_factory=list)
    # All departments the filter dropdown should show, independent of the
    # currently selected department, so the dropdown can switch freely.
    available_departments: list[str] = Field(default_factory=list)
