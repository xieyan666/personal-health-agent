"""Admin risk-case operations API (JWT + RBAC: admin roles only)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db
from backend.app.exceptions import ForbiddenError, ValidationError
from backend.app.models import User
from backend.app.schemas.risk_case import (
    LinkPlanRequest,
    LinkServiceRequest,
    RiskCaseActionOut,
    RiskCaseDetail,
    RiskCaseListResponse,
    RiskCaseOptions,
    StatusUpdateRequest,
)
from backend.app.services.risk_case_service import RiskCaseService, case_to_dict

router = APIRouter(prefix="/risk-cases", tags=["admin-risk-cases"])
admin = require_role("admin", "company_admin", "system_admin")


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValidationError):
        return HTTPException(400, str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(403, str(exc))
    return HTTPException(404, str(exc))


@router.get("", response_model=RiskCaseListResponse)
async def list_risk_cases(
    department: str | None = Query(default=None),
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    period: str = Query(default="30d", pattern="^(7d|30d|90d)$"),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    service = RiskCaseService(session)
    try:
        await service.sync_cases_from_assessments()
        days = {"7d": 7, "30d": 30, "90d": 90}[period]
        items = await service.list_cases(
            department=department, level=level, source=source, status=status, period_days=days,
        )
        stats = await service.stats(days)
        departments = await service.departments()
        return RiskCaseListResponse(stats=stats, items=[case_to_dict(case) for case in items], departments=departments)
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/options", response_model=RiskCaseOptions)
async def risk_case_options(
    case_id: UUID = Query(...),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    service = RiskCaseService(session)
    case = await service.get_case(case_id)
    options = await service.options(case.user_id)
    return RiskCaseOptions(**options)


@router.get("/{case_id}", response_model=RiskCaseDetail)
async def get_risk_case(
    case_id: UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    service = RiskCaseService(session)
    case = await service.get_case(case_id)
    actions = await service.get_case_actions(case_id)
    actor_ids = [action.actor_user_id for action in actions if action.actor_user_id]
    actor_names = await service.list_actor_names(actor_ids)
    payload = case_to_dict(case)
    payload["risk_summary"] = service.risk_summary(case)
    payload["actions"] = [
        {
            "id": action.id,
            "actor_user_id": action.actor_user_id,
            "actor_name": actor_names.get(action.actor_user_id),
            "action": action.action,
            "note": action.note,
            "created_at": action.created_at,
        }
        for action in actions
    ]
    return RiskCaseDetail(**payload)


@router.patch("/{case_id}/status", response_model=RiskCaseDetail)
async def update_risk_case_status(
    case_id: UUID,
    payload: StatusUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin),
):
    service = RiskCaseService(session)
    try:
        await service.transition(
            case_id, current_user.id,
            action=payload.action,
            note=payload.note,
            ignore_reason=payload.ignore_reason,
            next_review_days=payload.next_review_days,
        )
        return await get_risk_case(case_id, session, current_user)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{case_id}/actions", response_model=RiskCaseActionOut)
async def add_risk_case_action(
    case_id: UUID,
    payload: dict,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin),
):
    action = str(payload.get("action", "")).strip()
    note = payload.get("note")
    if not action:
        raise HTTPException(400, "action 不能为空")
    service = RiskCaseService(session)
    record = await service.add_action(case_id, current_user.id, action, note)
    return RiskCaseActionOut(
        id=record.id, actor_user_id=record.actor_user_id,
        actor_name=current_user.display_name, action=record.action,
        note=record.note, created_at=record.created_at,
    )


@router.post("/{case_id}/link-plan", response_model=RiskCaseDetail)
async def link_health_plan(
    case_id: UUID,
    payload: LinkPlanRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin),
):
    service = RiskCaseService(session)
    try:
        await service.link_plan(case_id, current_user.id, payload.plan_id)
        return await get_risk_case(case_id, session, current_user)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{case_id}/link-service", response_model=RiskCaseDetail)
async def link_health_service(
    case_id: UUID,
    payload: LinkServiceRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin),
):
    service = RiskCaseService(session)
    try:
        await service.link_service(case_id, current_user.id, payload.service_id)
        return await get_risk_case(case_id, session, current_user)
    except Exception as exc:
        raise _error(exc) from exc
