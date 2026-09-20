"""Personal-center contracts: read-only account info + editable profile fields."""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9\- ]{5,20}$")


class UserProfileResponse(BaseModel):
    id: UUID
    username: str
    display_name: str = ""
    email: str | None = None
    phone: str | None = None
    department: str | None = None
    job_title: str | None = None
    office_location: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    role: str
    status: str
    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """Whitelist of employee-editable fields. Everything else is rejected by the schema."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    department: str | None = Field(default=None, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    office_location: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=1000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("请输入有效的邮箱地址")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not PHONE_PATTERN.match(value):
            raise ValueError("请输入有效的手机号")
        return value

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @property
    def editable_fields(self) -> dict:
        return {key: value for key, value in self.model_dump(exclude_unset=True).items() if value is not None}


class ChangeMyPasswordRequest(BaseModel):
    """Password-change payload for the authenticated user only.

    Password values are deliberately never persisted or included in audit details.
    """

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("新密码需至少包含字母和数字")
        return value
