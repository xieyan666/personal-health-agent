"""Request/response contracts for AI health report interpretation.

``ReportAnalysisResponse`` is the strict schema used to validate DeepSeek
structured output before it is persisted.  Everything the model returns must
pass through this schema; invalid text is never stored as an analysis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class OverallAnalysis(BaseModel):
    level: Literal["good", "attention", "caution"]
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)


class ReportSummary(BaseModel):
    total_items: int = Field(ge=0)
    normal_count: int = Field(ge=0)
    attention_count: int = Field(ge=0)


class ReportFinding(BaseModel):
    item_name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=120)
    status: Literal["normal", "high", "low", "unknown"]
    description: str = Field(min_length=1, max_length=500)


class ReportAttention(BaseModel):
    item_name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=120)
    reference: str | None = Field(default=None, max_length=200)
    status: Literal["high", "low"]
    description: str = Field(min_length=1, max_length=600)
    source_type: str | None = Field(default=None, max_length=20)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ReportSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)


class ReportAnalysisResponse(BaseModel):
    overall: OverallAnalysis
    summary: ReportSummary
    findings: list[ReportFinding] = Field(default_factory=list)
    attention: list[ReportAttention] = Field(default_factory=list)
    suggestions: list[ReportSuggestion] = Field(default_factory=list)
    disclaimer: str = Field(default="AI健康解读仅用于健康管理辅助，不替代专业医疗诊断。", max_length=300)

    @field_validator("disclaimer")
    @classmethod
    def disclaimer_not_empty(cls, value: str) -> str:
        return (value or "AI健康解读仅用于健康管理辅助，不替代专业医疗诊断。").strip()


class HealthReportAnalysisResponse(BaseModel):
    analysis_id: UUID
    report_id: UUID
    status: str
    error_message: str | None = None
    analysis: ReportAnalysisResponse | None = None
    updated_at: datetime | None = None
    meta: dict | None = None


class HealthReportAnalysisTriggerResponse(BaseModel):
    analysis_id: UUID
    status: str
    cached: bool = False
