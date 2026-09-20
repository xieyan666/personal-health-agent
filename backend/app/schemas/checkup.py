"""Admin checkup-management contracts."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CheckupStats(BaseModel):
    total_reports: int = 0
    parsed_count: int = 0
    pending_review_reports: int = 0
    abnormal_reports: int = 0


class CheckupListItem(BaseModel):
    id: UUID
    employee_name: str | None = None
    employee_no: str | None = None
    department: str | None = None
    report_name: str
    hospital: str | None = None
    report_date: date | None = None
    uploaded_at: datetime
    parse_method: str | None = None
    parse_mode: str | None = None
    indicator_count: int = 0
    abnormal_count: int = 0
    parse_status: str
    display_status: str
    pending_review: bool = False
    ocr_used: bool = False
    parse_error: str | None = None


class IndicatorReviewOut(BaseModel):
    id: UUID
    item_name: str
    value: float
    value_text: str | None = None
    unit: str | None = None
    reference_text: str | None = None
    flag: str
    source_type: str
    confidence: float | None = None
    review_status: str | None = None
    reviewed_value: float | None = None
    review_note: str | None = None


class CheckupDetail(CheckupListItem):
    parse_warnings: dict | list | None = None
    parsed_at: datetime | None = None
    items: list[IndicatorReviewOut] = Field(default_factory=list)


class ParseDistributionItem(BaseModel):
    label: str
    count: int
    percent: float


class CheckupSummary(BaseModel):
    stats: CheckupStats = Field(default_factory=CheckupStats)
    status_distribution: list[ParseDistributionItem] = Field(default_factory=list)
    method_distribution: list[ParseDistributionItem] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    action: str = Field(description="confirm|modify|ignore")
    reviewed_value: float | None = None
    note: str | None = Field(default=None, max_length=300)
