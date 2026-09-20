"""Development-only wearable data for employee001 (idempotent)."""
import asyncio
from datetime import date, timedelta
from random import Random
from sqlalchemy import select
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import User, SleepRecord, ExerciseRecord, HeartRateRecord

async def main():
    async with AsyncSessionFactory() as db:
        user=await db.scalar(select(User).where(User.username=='employee001'))
        if not user: raise RuntimeError('employee001 not found')
        existing_sleep={x.record_date for x in (await db.scalars(select(SleepRecord).where(SleepRecord.user_id==user.id))).all()}
        existing_exercise={x.record_date for x in (await db.scalars(select(ExerciseRecord).where(ExerciseRecord.user_id==user.id))).all()}
        existing_heart={x.record_date for x in (await db.scalars(select(HeartRateRecord).where(HeartRateRecord.user_id==user.id))).all()}
        rng=Random(44); today=date.today()
        for i in range(60):
            d=today-timedelta(days=59-i); sleep=round(rng.uniform(6.2,7.8),1)
            if d not in existing_sleep: db.add(SleepRecord(user_id=user.id,record_date=d,sleep_duration=sleep,deep_sleep_duration=round(sleep*.28,1),light_sleep_duration=round(sleep*.65,1),sleep_quality='good' if sleep>=7 else 'fair',source='Wearable'))
            if d not in existing_exercise: db.add(ExerciseRecord(user_id=user.id,record_date=d,exercise_duration=rng.randint(25,75),steps=rng.randint(4000,11000),calories=rng.randint(180,500),exercise_type='walking',source='Wearable'))
            if d not in existing_heart: avg=rng.randint(65,82); db.add(HeartRateRecord(user_id=user.id,record_date=d,average_heart_rate=avg,resting_heart_rate=avg-7,max_heart_rate=avg+35,source='Wearable'))
        await db.commit(); print('health_records_seeded=60_days')
if __name__=='__main__': asyncio.run(main())
