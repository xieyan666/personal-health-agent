"""Current-user profile endpoints (personal center)."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.exceptions import NotFoundError
from backend.app.auth.security import hash_password, verify_password
from backend.app.models import AuditLog
from backend.app.schemas.user_profile import ChangeMyPasswordRequest, UserProfileResponse, UserProfileUpdate
from backend.app.services.avatar_storage import AvatarStorageService
from backend.app.services.user_profile_service import get_user_profile, update_user_avatar, update_user_profile
from backend.app.exceptions import ServiceError, ValidationError as AppValidationError

router = APIRouter(tags=["user-profile"])


@router.get("/users/me/profile", response_model=UserProfileResponse)
async def my_profile(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        return UserProfileResponse.model_validate(await get_user_profile(session, current_user.id))
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/users/me/profile", response_model=UserProfileResponse)
async def update_my_profile(payload: UserProfileUpdate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        return UserProfileResponse.model_validate(await update_user_profile(session, current_user.id, payload))
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, str(exc.errors())) from exc


@router.post("/users/me/change-password")
async def change_my_password(
    payload: ChangeMyPasswordRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Change the current JWT user's local password without exposing any secret."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    if payload.current_password == payload.new_password:
        raise HTTPException(400, "新密码不能与当前密码相同")

    current_user.password_hash = hash_password(payload.new_password)
    # Intentionally record only the security event, never a password or hash.
    session.add(AuditLog(
        actor_user_id=current_user.id,
        action="password_changed",
        resource_type="user",
        resource_id=current_user.id,
        risk_level="medium",
        safety_status="completed",
        outcome="success",
        details={},
    ))
    await session.commit()
    return {"status": "ok"}


@router.put("/users/me/avatar", response_model=UserProfileResponse)
async def upload_my_avatar(file: UploadFile = File(...), current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Upload an employee's avatar; the file remains private in MinIO."""
    try:
        user = await get_user_profile(session, current_user.id)
        storage = AvatarStorageService()
        previous_key = user.avatar_url
        object_key = storage.upload(user_id=current_user.id, content_type=file.content_type, data=await file.read())
        user = await update_user_avatar(session, current_user.id, object_key)
        storage.delete(previous_key)
        return UserProfileResponse.model_validate(user)
    except AppValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/users/me/avatar")
async def get_my_avatar(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Stream the avatar only after JWT authentication; no public object URL."""
    user = await get_user_profile(session, current_user.id)
    if not user.avatar_url:
        raise HTTPException(404, "尚未上传头像")
    try:
        data, content_type = AvatarStorageService().read(user.avatar_url)
        return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=300"})
    except (AppValidationError, ServiceError) as exc:
        raise HTTPException(404, "头像暂不可用") from exc
