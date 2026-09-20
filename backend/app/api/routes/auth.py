from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db
from backend.app.auth.jwt import create_access_token, create_refresh_token, get_current_user
from backend.app.auth.security import verify_password
from backend.app.repositories.user import UserRepository
from backend.app.schemas.auth import AuthUser, LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    user = await UserRepository(session).get_by_username(payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号已被禁用，请联系企业管理员")
    return LoginResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user), user=AuthUser.model_validate(user))

@router.get("/me", response_model=AuthUser)
async def me(user=Depends(get_current_user)):
    return AuthUser.model_validate(user)
