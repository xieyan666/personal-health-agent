from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.models import HealthProfile
from backend.app.schemas.health_profile import HealthProfileResponse, HealthProfileUpdate
router = APIRouter(prefix="/health/profile", tags=["health-profile"])
def to_response(profile, user_id):
    bmi = None
    if profile is not None and profile.height and profile.weight:
        bmi = round(float(profile.weight) / ((float(profile.height) / 100) ** 2), 1)
    return HealthProfileResponse(user_id=user_id, username="", age=getattr(profile, "age", None), gender=getattr(profile, "gender", None), height=getattr(profile, "height", None), weight=getattr(profile, "weight", None), bmi=bmi)
@router.get("", response_model=HealthProfileResponse)
async def get_profile(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    result = to_response(await session.scalar(select(HealthProfile).where(HealthProfile.user_id == current_user.id)), current_user.id)
    result.username = current_user.username
    return result
@router.put("", response_model=HealthProfileResponse)
async def update_profile(payload: HealthProfileUpdate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    profile = await session.scalar(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    if profile is None:
        profile = HealthProfile(user_id=current_user.id, **payload.model_dump()); session.add(profile)
    else:
        for key, value in payload.model_dump().items(): setattr(profile, key, value)
    await session.commit(); await session.refresh(profile)
    result = to_response(profile, current_user.id)
    result.username = current_user.username
    return result
