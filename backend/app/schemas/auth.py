from uuid import UUID
from pydantic import BaseModel, ConfigDict

class LoginRequest(BaseModel):
    username: str
    password: str
    model_config = ConfigDict(extra="forbid")

class AuthUser(BaseModel):
    id: UUID
    username: str
    role: str
    display_name: str = ""
    avatar_url: str | None = None
    company_id: str | None = None
    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUser
