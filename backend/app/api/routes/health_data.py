from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.models import HealthProfile, SleepRecord, ExerciseRecord, HeartRateRecord
from backend.app.schemas.health_data import HealthSummaryResponse, HealthTrendsResponse
router = APIRouter(prefix="/health", tags=["health-data"])
def d(v): return v.isoformat()
@router.get("/trends", response_model=HealthTrendsResponse)
async def trends(days: int = Query(30, ge=1, le=366), start_date: date | None = None, end_date: date | None = None, current_user=Depends(get_current_user), session: AsyncSession=Depends(get_db)):
    end = end_date or date.today(); start = start_date or (end - timedelta(days=days-1))
    scope=lambda model: select(model).where(model.user_id==current_user.id, model.record_date >= start, model.record_date <= end).order_by(model.record_date)
    sleep=(await session.scalars(scope(SleepRecord))).all(); exercise=(await session.scalars(scope(ExerciseRecord))).all(); heart=(await session.scalars(scope(HeartRateRecord))).all()
    return {"sleep":[{"date":d(x.record_date),"sleep_duration":x.sleep_duration,"quality":x.sleep_quality,"source":x.source} for x in sleep],"exercise":[{"date":d(x.record_date),"duration":x.exercise_duration,"steps":x.steps,"source":x.source} for x in exercise],"heart_rate":[{"date":d(x.record_date),"average":x.average_heart_rate,"resting":x.resting_heart_rate,"source":x.source} for x in heart]}
@router.get("/summary", response_model=HealthSummaryResponse)
async def summary(current_user=Depends(get_current_user), session: AsyncSession=Depends(get_db)):
    p=await session.scalar(select(HealthProfile).where(HealthProfile.user_id==current_user.id))
    avg_sleep=await session.scalar(select(func.avg(SleepRecord.sleep_duration)).where(SleepRecord.user_id==current_user.id))
    avg_ex=await session.scalar(select(func.avg(ExerciseRecord.exercise_duration)).where(ExerciseRecord.user_id==current_user.id))
    avg_hr=await session.scalar(select(func.avg(HeartRateRecord.average_heart_rate)).where(HeartRateRecord.user_id==current_user.id))
    bmi = round(float(p.weight)/((float(p.height)/100)**2),1) if p and p.height and p.weight else None
    return {"profile":{"age":p.age if p else None,"gender":p.gender if p else None,"bmi":bmi},"sleep":{"avg_sleep":round(float(avg_sleep),1) if avg_sleep is not None else None},"exercise":{"avg_duration":round(float(avg_ex),1) if avg_ex is not None else None},"heart_rate":{"avg_hr":round(float(avg_hr),1) if avg_hr is not None else None}}
