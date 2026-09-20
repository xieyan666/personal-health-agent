"""Request/response contracts for mental wellness."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MentalCheckinCreate(BaseModel):
    mood: str = Field(default="一般", max_length=20)
    stress_level: int = Field(ge=1, le=10)
    energy_level: int = Field(ge=1, le=10)
    sleep_feeling: str = Field(default="一般", max_length=20)
    stress_sources: list[str] = Field(default_factory=list, max_length=20)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("mood", "sleep_feeling")
    @classmethod
    def non_empty(cls, value: str) -> str:
        return value.strip() or "一般"


class MentalCheckinResponse(BaseModel):
    id: UUID
    checkin_date: date
    mood: str
    stress_level: int
    energy_level: int
    sleep_feeling: str
    stress_sources: list[str] = Field(default_factory=list)
    note: str | None = None


class MentalTrendPoint(BaseModel):
    date: str
    value: float


class MentalTrendResponse(BaseModel):
    type: str
    period: int
    average: float = 0.0
    change: float = 0.0
    data: list[MentalTrendPoint] = Field(default_factory=list)


class StressSourceShare(BaseModel):
    name: str
    percent: float


class MentalWorkloadResponse(BaseModel):
    week_avg_stress: float = 0.0
    high_stress_days: int = 0
    avg_energy: float = 0.0
    recovery_status: str = "暂无数据"
    stress_sources: list[StressSourceShare] = Field(default_factory=list)
    has_data: bool = False


class MentalAssessmentResponse(BaseModel):
    id: UUID
    assessment_type: str
    assessment_version: str
    score: int | None = None
    raw_score: int | None = None
    percentage_score: int | None = None
    level: str | None = None
    needs_follow_up: bool = False
    safety_flag: bool = False
    safety_reason: str | None = None
    result_summary: dict | None = None
    completed_at: datetime | None = None


class MentalAssessmentOption(BaseModel):
    label: str
    value: int


class MentalAssessmentQuestion(BaseModel):
    id: str
    order: int
    text: str
    required: bool = True
    options: list[MentalAssessmentOption] = Field(default_factory=list)
    safety_sensitive: bool = False


class MentalAssessmentDefinitionResponse(BaseModel):
    assessment_type: str
    version: str
    name: str
    title: str
    description: str
    question_count: int
    estimated_minutes: int
    estimated_duration: str | None = None
    result_usage: str
    disclaimer: str
    questionnaire_status: str
    period: str = "过去两周"
    source: dict = Field(default_factory=dict)
    enabled: bool = False
    result_note: str | None = None
    questions: list[MentalAssessmentQuestion] = Field(default_factory=list)


class MentalAssessmentAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    value: int


class MentalAssessmentCreate(BaseModel):
    assessment_type: str = Field(pattern="^(WHO-5|PSS-10|GAD-7|PHQ-9)$")
    assessment_version: str = Field(min_length=1, max_length=64)
    answers: list[MentalAssessmentAnswer] = Field(default_factory=list)
