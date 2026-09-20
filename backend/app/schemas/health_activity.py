"""Request/response contracts for the enterprise health-activity operations
(admin activity ops + employee activity enrollment)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ActivityBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    activity_type: str = Field(default="lecture", max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    start_date: date | None = None
    end_date: date | None = None
    start_time: str | None = Field(default=None, max_length=10)
    end_time: str | None = Field(default=None, max_length=10)
    registration_deadline: datetime | None = None
    delivery_mode: str = Field(default="offline", max_length=20)
    location: str | None = Field(default=None, max_length=200)
    scope: str = Field(default="all", max_length=20)
    target_department: str | None = Field(default=None, max_length=120)
    organizer: str | None = Field(default=None, max_length=80)
    contact_person: str | None = Field(default=None, max_length=80)
    capacity: int | None = Field(default=None, ge=1, le=100000)

    @model_validator(mode="after")
    def _check_ranges(self) -> "ActivityBase":
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("活动结束日期不能早于开始日期")
        if self.scope == "department" and not self.target_department:
            raise ValueError("参与范围为指定部门时必须填写部门")
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("人数上限必须大于 0")
        return self


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(ActivityBase):
    pass


class ActivityListItem(BaseModel):
    id: UUID
    name: str
    activity_type: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    start_time: str | None = None
    end_time: str | None = None
    registration_deadline: datetime | None = None
    delivery_mode: str = "offline"
    location: str | None = None
    scope: str = "all"
    target_department: str | None = None
    organizer: str | None = None
    contact_person: str | None = None
    capacity: int | None = None
    participants: int = 0
    remaining: int | None = None
    status: str = "draft"
    display_status: str = "draft"
    joined: bool = False
    created_at: datetime | None = None


class ActivityDetail(ActivityListItem):
    pass


class ParticipantItem(BaseModel):
    id: UUID
    user_id: UUID
    employee_no: str | None = None
    employee_name: str | None = None
    department: str | None = None
    joined_at: datetime | None = None
    status: str = "joined"


class AdminActivitySummary(BaseModel):
    month_activity_count: int = 0
    open_registration_count: int = 0
    total_participants: int = 0
    avg_participation_rate: float = 0.0
