"""Seed development test data: ~30 days of mental check-ins for employee001.

Idempotent; existing rows for the same dates are skipped (unique user+date).

    docker exec -e PYTHONPATH=/app life-health-agent-api sh -c \
      "cd /app/backend && python3 -m scripts.seed_mental_checkins"
"""

import asyncio
from datetime import date, timedelta
from random import Random

from sqlalchemy import select
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import MentalCheckin, User

MOODS = ["很好", "不错", "不错", "一般", "一般", "有压力", "状态较差"]
SLEEP_FEELINGS = ["很好", "不错", "一般", "较差"]
SOURCES_POOL = ["工作任务", "睡眠不足", "人际沟通", "家庭", "身体状态", "经济压力"]


async def main() -> None:
    async with AsyncSessionFactory() as session:
        user = await session.scalar(select(User).where(User.username == "employee001"))
        if user is None:
            print("employee001 not found; skip")
            return
        existing_dates = set(
            (
                await session.scalars(
                    select(MentalCheckin.checkin_date).where(MentalCheckin.user_id == user.id)
                )
            ).all()
        )
        rng = Random(20260826)
        inserted = 0
        for offset in range(30):
            day = date.today() - timedelta(days=offset)
            if day in existing_dates:
                continue
            # Recent days are more stressful (workload peak), matching the demo.
            stress = rng.randint(4, 8) if offset <= 7 else rng.randint(3, 6)
            energy = rng.randint(4, 7) if offset <= 7 else rng.randint(5, 8)
            mood = "有压力" if stress >= 7 else "一般" if stress >= 5 else "不错"
            sources = rng.sample(SOURCES_POOL, k=rng.randint(1, 3))
            session.add(MentalCheckin(
                user_id=user.id,
                checkin_date=day,
                mood=mood,
                stress_level=stress,
                energy_level=energy,
                sleep_feeling=rng.choice(SLEEP_FEELINGS),
                stress_sources=sources,
                note="开发测试数据" if offset > 0 else None,
            ))
            inserted += 1
        await session.commit()
        print(f"Inserted {inserted} check-ins for employee001 (existing {len(existing_dates)} days kept)")


if __name__ == "__main__":
    asyncio.run(main())
