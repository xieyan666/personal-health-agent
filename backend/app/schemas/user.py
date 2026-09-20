"""User API schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.app.schemas.common import ORMResponse


class UserCreate(BaseModel):
    username: str
    phone: Optional[str] = None
    display_name: str
    department: Optional[str] = None
    company_id: Optional[str] = None
    role: str = "employee"
    email: Optional[str] = None
    auth_source: str
    external_user_id: Optional[str] = None
    status: str = "active"
    timezone: str = "Asia/Shanghai"

    model_config = ConfigDict(extra="forbid")


class UserUpdate(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    auth_source: Optional[str] = None
    external_user_id: Optional[str] = None
    status: Optional[str] = None
    timezone: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class UserResponse(ORMResponse):
    id: UUID
    username: str
    phone: Optional[str]
    display_name: str
    department: Optional[str]
    company_id: Optional[str]
    role: str
    email: Optional[str]
    auth_source: str
    external_user_id: Optional[str]
    status: str
    timezone: str
    created_at: datetime
    updated_at: datetime
