from datetime import date
from typing import Any
from pydantic import BaseModel
class HealthTrendsResponse(BaseModel):
    sleep: list[dict[str, Any]]
    exercise: list[dict[str, Any]]
    heart_rate: list[dict[str, Any]]
class HealthSummaryResponse(BaseModel):
    profile: dict[str, Any]
    sleep: dict[str, Any]
    exercise: dict[str, Any]
    heart_rate: dict[str, Any]
