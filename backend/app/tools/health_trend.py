from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models import SleepRecord, ExerciseRecord, HeartRateRecord
from backend.app.services.data_authorization_service import AuthorizationService

async def get_health_trend(session: AsyncSession, user_id, days: int = 30, start_date: date | None = None, end_date: date | None = None):
    end = end_date or date.today(); start = start_date or (end - timedelta(days=days - 1))
    def scope(model): return select(model).where(model.user_id == user_id, model.record_date >= start, model.record_date <= end).order_by(model.record_date)
    sleep=(await session.scalars(scope(SleepRecord))).all(); exercise=(await session.scalars(scope(ExerciseRecord))).all(); heart=(await session.scalars(scope(HeartRateRecord))).all()
    return {'sleep':[{'date':x.record_date.isoformat(),'value':x.sleep_duration} for x in sleep], 'exercise':[{'date':x.record_date.isoformat(),'duration':x.exercise_duration,'steps':x.steps} for x in exercise], 'heart_rate':[{'date':x.record_date.isoformat(),'value':x.average_heart_rate} for x in heart]}


async def get_authorized_health_trend(session: AsyncSession, user_id, *, agent_id: str, purpose: str, days: int = 30):
    """Tool boundary for wearable trends; one audit row is written per data category."""
    authorization = AuthorizationService(session)
    for scope in ("wearable.sleep.read", "wearable.exercise.read", "wearable.heart_rate.read"):
        await authorization.require(user_id=user_id, grantee_type="agent", grantee_id=agent_id, scope=scope, purpose=purpose)
    return await get_health_trend(session, user_id, days=days)
