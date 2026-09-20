"""Health plan business operations: ownership, tasks, status and stats.

All queries are scoped by the JWT user id; a plan owned by another employee
raises ForbiddenError so no cross-user data can leak.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import ForbiddenError, NotFoundError
from backend.app.models import HealthPlan, HealthPlanTask

PLAN_STATUSES = {"draft", "active", "paused", "completed", "cancelled"}
TASK_STATUSES = {"pending", "completed", "skipped"}


async def get_owned_plan(session: AsyncSession, plan_id: UUID, user_id: UUID) -> HealthPlan:
    plan = await session.get(HealthPlan, plan_id)
    if plan is None:
        raise NotFoundError("健康计划不存在")
    if plan.user_id != user_id:
        raise ForbiddenError("无权访问其他员工的健康计划")
    return plan


async def list_plans(session: AsyncSession, user_id: UUID) -> list[HealthPlan]:
    return list(
        (
            await session.scalars(
                select(HealthPlan)
                .where(HealthPlan.user_id == user_id)
                .order_by(HealthPlan.created_at.desc())
            )
        ).all()
    )


async def get_current_plan(session: AsyncSession, user_id: UUID) -> HealthPlan | None:
    """Return the active (or paused, as fallback) plan for the user."""
    for status in ("active", "paused"):
        plan = await session.scalar(
            select(HealthPlan)
            .where(HealthPlan.user_id == user_id, HealthPlan.status == status)
            .order_by(HealthPlan.created_at.desc())
            .limit(1)
        )
        if plan is not None:
            return plan
    return None


async def get_plan_tasks(session: AsyncSession, plan_id: UUID, user_id: UUID) -> list[HealthPlanTask]:
    await get_owned_plan(session, plan_id, user_id)
    return list(
        (
            await session.scalars(
                select(HealthPlanTask)
                .where(HealthPlanTask.plan_id == plan_id, HealthPlanTask.user_id == user_id)
                .order_by(HealthPlanTask.day_index, HealthPlanTask.created_at)
            )
        ).all()
    )


async def get_owned_task(session: AsyncSession, task_id: UUID, user_id: UUID) -> HealthPlanTask:
    task = await session.get(HealthPlanTask, task_id)
    if task is None:
        raise NotFoundError("健康计划任务不存在")
    if task.user_id != user_id:
        raise ForbiddenError("无权访问其他员工的计划任务")
    return task


async def complete_task(session: AsyncSession, task_id: UUID, user_id: UUID, *, completed: bool) -> HealthPlanTask:
    task = await get_owned_task(session, task_id, user_id)
    if completed:
        task.completion_status = "completed"
        task.completion_source = "manual"
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.completion_status = "pending"
        task.completion_source = "manual"
        task.completed_at = None
        task.actual_value = None
    await session.commit()
    await session.refresh(task)
    return task


async def update_plan_status(session: AsyncSession, plan_id: UUID, user_id: UUID, status: str) -> HealthPlan:
    if status not in PLAN_STATUSES:
        raise NotFoundError("计划状态无效")
    plan = await get_owned_plan(session, plan_id, user_id)
    plan.status = status
    await session.commit()
    await session.refresh(plan)
    return plan


def _current_day(plan: HealthPlan, today: date) -> int:
    """1-based day index for today within the plan window."""
    if plan.start_date is None or today < plan.start_date:
        return 1
    elapsed = (today - plan.start_date).days
    return min(max(elapsed + 1, 1), max(plan.duration_days, 1))


def compute_plan_stats(tasks: list[HealthPlanTask], duration_days: int) -> dict:
    """Compute real statistics from persisted task states.

    task_completion_rate  = completed / total
    executed_days         = distinct days having >=1 completed task
    streak_days           = consecutive days (from today backwards) with a completion
    """
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task.completion_status == "completed")
    executed_day_indexes = sorted(
        {task.day_index for task in tasks if task.completion_status == "completed"}
    )
    rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks else 0.0
    streak = 0
    if executed_day_indexes:
        expected = executed_day_indexes[-1]
        for day in reversed(executed_day_indexes):
            if day == expected:
                streak += 1
                expected -= 1
            else:
                break
    return {
        "executed_days": len(executed_day_indexes),
        "total_days": max(duration_days, 1),
        "task_completion_rate": rate,
        "streak_days": streak,
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
    }
