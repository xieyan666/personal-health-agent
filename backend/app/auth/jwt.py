import os
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.repositories.user import UserRepository

SECRET = os.getenv("JWT_SECRET", "local-development-jwt-secret-change-me")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_bearer = HTTPBearer(auto_error=False)

def create_token(user, minutes: int, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "username": user.username, "role": user.role,
               "company_id": user.company_id, "type": token_type, "iat": now,
               "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

def create_access_token(user) -> str:
    return create_token(user, 60, "access")

def create_refresh_token(user) -> str:
    return create_token(user, 60 * 24 * 30, "refresh")

async def get_current_user(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_db)):
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        user_id = UUID(payload["sub"])
        if payload.get("type") != "access":
            raise error
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise error
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号已被禁用，请联系企业管理员")
    return user

async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    session: AsyncSession = Depends(get_db),
):
    """Authenticate when a bearer token is supplied, preserving legacy CRUD callers."""
    if credentials is None:
        return None
    return await get_current_user(credentials.credentials, session)

def require_role(*roles: str):
    async def dependency(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
