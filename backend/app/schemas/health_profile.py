from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
class HealthProfileUpdate(BaseModel):
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[str] = None
    height: Optional[float] = Field(default=None, gt=0, le=300)
    weight: Optional[float] = Field(default=None, gt=0, le=500)
class HealthProfileResponse(HealthProfileUpdate):
    user_id: UUID
    username: str
    bmi: Optional[float] = None
