"""Seed development test data: a 7-day sleep-improvement plan for employee001.

Marked explicitly as development test data.  Idempotent: re-running does not
duplicate plans.

    docker exec -e PYTHONPATH=/app life-health-agent-api sh -c \
      "cd /app/backend && python3 -m scripts.seed_health_plan"
"""

import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import select
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import HealthPlan, HealthPlanTask, User

PLAN_NAME = "7天睡眠改善计划"

# (day_index, title, task_type, target_value) — 2-4 tasks per day.
DAYS = {
    1: [("23:30前准备入睡", "sleep", None), ("步行20分钟", "exercise", "20 min"), ("睡前30分钟减少电子设备使用", "sleep", None)],
    2: [("固定起床时间07:00", "sleep", "07:00"), ("轻度运动20分钟", "exercise", "20 min"), ("睡前5分钟放松练习", "mental", None)],
    3: [("23:00前准备入睡", "sleep", None), ("午休后步行20分钟", "exercise", "20 min"), ("记录今日睡眠时长", "sleep", None)],
    4: [("固定起床时间07:00", "sleep", "07:00"), ("今日累计运动30分钟", "exercise", "30 min"), ("睡前30分钟泡脚放松", "sleep", None), ("完成心理状态打卡", "mental", None)],
    5: [("23:30前准备入睡", "sleep", None), ("步行30分钟", "exercise", "30 min"), ("睡前减少屏幕使用", "sleep", None)],
    6: [("固定起床时间07:00", "sleep", "07:00"), ("轻度运动20分钟", "exercise", "20 min"), ("睡前5分钟放松练习", "mental", None)],
    7: [("复盘一周睡眠规律", "mental", None), ("保持23:30前入睡", "sleep", None), ("完成心理状态打卡", "mental", None)],
}


async def main() -> None:
    async with AsyncSessionFactory() as session:
        user = await session.scalar(select(User).where(User.username == "employee001"))
        if user is None:
            print("employee001 not found; skip seeding")
            return
        existing = await session.scalar(
            select(HealthPlan).where(
                HealthPlan.user_id == user.id,
                HealthPlan.plan_name == PLAN_NAME,
                HealthPlan.source_agent == "health_plan_agent",
            )
        )
        if existing is not None:
            print(f"Plan already exists: {existing.id}; skip")
            return

        # Start 3 days ago so the demo has completed days 1-3 and today = Day 4.
        start = date.today() - timedelta(days=3)
        plan = HealthPlan(
            user_id=user.id,
            plan_name=PLAN_NAME,
            plan_type="sleep",
            goal="改善睡眠：平均睡眠 ≥7小时，23:30前准备入睡，减少睡前屏幕使用",
            duration_days=7,
            start_date=start,
            end_date=start + timedelta(days=6),
            status="active",
            source_agent="health_plan_agent",
            source_input={"seed": "development-test-data"},
        )
        session.add(plan)
        await session.flush()

        today = date.today()
        for day_index, tasks in DAYS.items():
            task_date = start + timedelta(days=day_index - 1)
            for title, task_type, target in tasks:
                completed = task_date < today
                actual = None
                if task_date == today and title == "今日累计运动30分钟":
                    # Demo partial progress on today's task.
                    completed = False
                    actual = "18 / 30 min"
                session.add(
                    HealthPlanTask(
                        plan_id=plan.id,
                        user_id=user.id,
                        day_index=day_index,
                        task_date=task_date,
                        task_type=task_type,
                        title=title,
                        description=f"{title}（{PLAN_NAME} Day{day_index}）",
                        target_value=target,
                        actual_value=actual,
                        completion_status="completed" if completed else "pending",
                        completion_source="manual",
                        completed_at=datetime.now() if completed else None,
                    )
                )
        await session.commit()
        from backend.app.services.notification_service import create_notification
        await create_notification(
            session,
            user.id,
            "health_plan",
            "健康计划已生成",
            f"新的健康改善计划「{PLAN_NAME}」已生成，可从健康计划页面查看与执行。",
            "/employee/plan",
        )
        print(f"Seeded plan {plan.id}: {PLAN_NAME} for employee001 (start={start}, today=Day4)")


if __name__ == "__main__":
    asyncio.run(main())
