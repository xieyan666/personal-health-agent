"""Safely remove the demo analytics employees (analytics-demo-%).

Only deletes rows owned by analytics-demo-* users. Real employees
(employee001, admin001, and any other non-demo user) are never touched.

Run manually:
    cd backend && python -m scripts.clear_health_analytics_demo
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, select

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import (
    Employee,
    HealthCheckReport,
    HealthPlan,
    HealthPlanTask,
    HealthProfile,
    HealthRiskScore,
    MentalCheckin,
    RiskAssessment,
    User,
)


async def main() -> None:
    async with AsyncSessionFactory() as session:
        demo_user_ids = list(
            (
                await session.scalars(
                    select(User.id).where(User.username.like("analytics-demo-%"))
                )
            ).all()
        )
        if not demo_user_ids:
            print("no demo users found, nothing to clean")
            return
        for model in (HealthPlanTask, HealthPlan, MentalCheckin, RiskAssessment, HealthRiskScore, HealthCheckReport, HealthProfile, Employee):
            await session.execute(
                delete(model).where(model.user_id.in_(demo_user_ids))
            )
        await session.execute(delete(User).where(User.id.in_(demo_user_ids)))
        await session.commit()
        print(f"removed {len(demo_user_ids)} demo users and all their demo health data")


if __name__ == "__main__":
    asyncio.run(main())
