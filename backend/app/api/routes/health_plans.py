"""Authenticated health-plan APIs: current plan, tasks and execution actions."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.exceptions import ForbiddenError, NotFoundError
from backend.app.schemas.health_plans import HealthPlanResponse, HealthPlanStats, HealthPlanSummaryResponse, HealthPlanTaskResponse
from backend.app.services.health_plan_service import (
    complete_task,
    compute_plan_stats,
    get_current_plan,
    get_owned_plan,
    get_owned_task,
    get_plan_tasks,
    list_plans,
    update_plan_status,
)

router = APIRouter(tags=["health-plans"])


def _task_to_response(task) -> HealthPlanTaskResponse:
    return HealthPlanTaskResponse(
        id=task.id,
        plan_id=task.plan_id,
        day_index=task.day_index,
        task_date=task.task_date,
        task_type=task.task_type,
        title=task.title,
        description=task.description,
        target_value=task.target_value,
        actual_value=task.actual_value,
        completion_status=task.completion_status,
        completion_source=task.completion_source,
        completed_at=task.completed_at,
    )


def _plan_to_response(plan, tasks, *, with_stats: bool = True) -> HealthPlanResponse:
    stats = None
    if with_stats:
        computed = compute_plan_stats(tasks, plan.duration_days)
        stats = HealthPlanStats(**computed)
    today = date.today()
    current_day = None
    if plan.start_date <= today <= plan.end_date:
        current_day = min((today - plan.start_date).days + 1, plan.duration_days)
    return HealthPlanResponse(
        id=plan.id,
        plan_name=plan.plan_name,
        plan_type=plan.plan_type,
        goal=plan.goal,
        duration_days=plan.duration_days,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        source_agent=plan.source_agent,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        tasks=[_task_to_response(task) for task in tasks],
        stats=stats,
        current_day=current_day,
    )


def _plan_to_summary(plan, tasks) -> HealthPlanSummaryResponse:
    computed = compute_plan_stats(tasks, plan.duration_days)
    return HealthPlanSummaryResponse(
        id=plan.id,
        plan_name=plan.plan_name,
        plan_type=plan.plan_type,
        goal=plan.goal,
        duration_days=plan.duration_days,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        source_agent=plan.source_agent,
        created_at=plan.created_at,
        stats=HealthPlanStats(**computed),
    )


async def _handle(fn):
    try:
        return await fn()
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/health-plans/current", response_model=HealthPlanResponse)
async def current_plan(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        plan = await get_current_plan(session, current_user.id)
        if plan is None:
            now = datetime.now()
            return HealthPlanResponse(
                id=UUID(int=0), plan_name="", plan_type="general", goal=None,
                duration_days=0, start_date=date.today(), end_date=date.today(),
                status="none", source_agent="health_plan_agent",
                created_at=now, updated_at=now,
            )
        tasks = await get_plan_tasks(session, plan.id, current_user.id)
        return _plan_to_response(plan, tasks)
    return await _handle(action)


@router.get("/health-plans", response_model=list[HealthPlanSummaryResponse])
async def list_all_plans(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        plans = await list_plans(session, current_user.id)
        return [_plan_to_summary(plan, await get_plan_tasks(session, plan.id, current_user.id)) for plan in plans]
    return await _handle(action)


@router.get("/health-plans/{plan_id}", response_model=HealthPlanResponse)
async def plan_detail(plan_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        plan = await get_owned_plan(session, plan_id, current_user.id)
        tasks = await get_plan_tasks(session, plan.id, current_user.id)
        return _plan_to_response(plan, tasks)
    return await _handle(action)


@router.get("/health-plans/{plan_id}/tasks", response_model=list[HealthPlanTaskResponse])
async def plan_tasks(plan_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        tasks = await get_plan_tasks(session, plan_id, current_user.id)
        return [_task_to_response(task) for task in tasks]
    return await _handle(action)


@router.patch("/health-plan-tasks/{task_id}/complete", response_model=HealthPlanTaskResponse)
async def complete_plan_task(task_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return _task_to_response(await complete_task(session, task_id, current_user.id, completed=True))
    return await _handle(action)


@router.patch("/health-plan-tasks/{task_id}/uncomplete", response_model=HealthPlanTaskResponse)
async def uncomplete_plan_task(task_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return _task_to_response(await complete_task(session, task_id, current_user.id, completed=False))
    return await _handle(action)


@router.patch("/health-plans/{plan_id}/pause", response_model=HealthPlanResponse)
async def pause_plan(plan_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        plan = await update_plan_status(session, plan_id, current_user.id, "paused")
        tasks = await get_plan_tasks(session, plan.id, current_user.id)
        return _plan_to_response(plan, tasks)
    return await _handle(action)


@router.patch("/health-plans/{plan_id}/resume", response_model=HealthPlanResponse)
async def resume_plan(plan_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        plan = await update_plan_status(session, plan_id, current_user.id, "active")
        tasks = await get_plan_tasks(session, plan.id, current_user.id)
        return _plan_to_response(plan, tasks)
    return await _handle(action)


@router.patch("/health-plans/{plan_id}/complete", response_model=HealthPlanResponse)
async def complete_plan(plan_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        plan = await update_plan_status(session, plan_id, current_user.id, "completed")
        tasks = await get_plan_tasks(session, plan.id, current_user.id)
        return _plan_to_response(plan, tasks)
    return await _handle(action)
