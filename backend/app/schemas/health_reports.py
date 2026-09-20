"""Request/response contracts for employee health-check reports."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HealthCheckIndicatorInput(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=80)
    item_name: str = Field(min_length=1, max_length=120)
    value: float
    unit: str | None = Field(default=None, max_length=40)
    value_text: str | None = Field(default=None, max_length=100)
    reference_min: float | None = None
    reference_max: float | None = None
    reference_text: str | None = Field(default=None, max_length=100)
    source_page: int | None = None
    source_type: str = "text"
    confidence: float | None = None


class HealthCheckReportCreate(BaseModel):
    report_name: str = Field(min_length=1, max_length=200)
    hospital: str | None = Field(default=None, max_length=200)
    report_date: date
    indicators: list[HealthCheckIndicatorInput] = Field(default_factory=list)


class HealthCheckIndicatorResponse(HealthCheckIndicatorInput):
    id: UUID
    flag: str


class HealthCheckReportResponse(BaseModel):
    id: UUID
    report_name: str
    hospital: str | None
    report_date: date
    file_name: str | None
    parse_status: str
    parse_progress: int = Field(ge=0, le=100)
    parse_error: str | None = None
    parse_mode: str | None = None
    ocr_used: bool = False
    parse_warnings: list[str] = Field(default_factory=list)
    parsed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    indicators: list[HealthCheckIndicatorResponse] = Field(default_factory=list)
    analysis: dict | None = None
