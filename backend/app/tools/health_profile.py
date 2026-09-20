from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models import HealthProfile, SleepRecord, ExerciseRecord, HeartRateRecord
from backend.app.services.data_authorization_service import AuthorizationService

async def get_health_profile_context(session: AsyncSession, user_id):
    profile = await session.scalar(select(HealthProfile).where(HealthProfile.user_id == user_id))
    sleep = await session.scalar(select(func.avg(SleepRecord.sleep_duration)).where(SleepRecord.user_id == user_id))
    exercise = await session.scalar(select(func.avg(ExerciseRecord.exercise_duration)).where(ExerciseRecord.user_id == user_id))
    heart = await session.scalar(select(func.avg(HeartRateRecord.average_heart_rate)).where(HeartRateRecord.user_id == user_id))
    bmi = round(float(profile.weight) / ((float(profile.height) / 100) ** 2), 1) if profile and profile.height and profile.weight else None
    return {"profile": {"age": profile.age if profile else None, "gender": profile.gender if profile else None, "bmi": bmi}, "sleep": {"avg_sleep": round(float(sleep), 1) if sleep is not None else None}, "exercise": {"avg_duration": round(float(exercise), 1) if exercise is not None else None}, "heart_rate": {"avg_hr": round(float(heart), 1) if heart is not None else None}}


async def get_authorized_health_profile_context(session: AsyncSession, user_id, *, agent_id: str, purpose: str):
    """Tool boundary for profile access; UI profile pages use the unwrapped owner query."""
    await AuthorizationService(session).require(user_id=user_id, grantee_type="agent", grantee_id=agent_id, scope="health_profile.read", purpose=purpose)
    return await get_health_profile_context(session, user_id)


async def get_report_profile_context(session: AsyncSession, user_id):
    """HealthProfileTool payload for report interpretation.

    Returns age/gender/height/weight/BMI with None for missing fields.  The
    agent must treat missing data as unavailable and must not fabricate it.
    """
    profile = await session.scalar(select(HealthProfile).where(HealthProfile.user_id == user_id))
    if profile is None:
        return {"age": None, "gender": None, "height": None, "weight": None, "bmi": None}
    height = float(profile.height) if profile.height is not None else None
    weight = float(profile.weight) if profile.weight is not None else None
    bmi = round(weight / ((height / 100) ** 2), 1) if height and weight else None
    return {
        "age": profile.age,
        "gender": profile.gender,
        "height": height,
        "weight": weight,
        "bmi": bmi,
    }
