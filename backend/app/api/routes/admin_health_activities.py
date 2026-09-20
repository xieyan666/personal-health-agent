"""Admin health-activity operations API (JWT + RBAC: admin roles only)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db
from backend.app.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.app.models import User
from backend.app.schemas.health_activity import (
    ActivityCreate,
    ActivityDetail,
    ActivityListItem,
    ActivityUpdate,
    AdminActivitySummary,
    ParticipantItem,
)
from backend.app.services.health_activity_service import (
    admin_activity_dynamics,
    admin_cancel_activity,
    admin_create_activity,
    admin_finish_activity,
    admin_get_activity,
    admin_list_activities,
    admin_list_participants,
    admin_publish_activity,
    admin_summary,
    admin_update_activity,
)

router = APIRouter(prefix="/health-activities", tags=["admin-health-activities"])
admin = require_role("admin", "company_admin", "system_admin")


def _handle(action):
    try:
        return action()
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/summary", response_model=AdminActivitySummary)
async def activity_summary(session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_summary(session))


@router.get("/dynamics")
async def activity_dynamics(
    limit: int = Query(default=12, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    return await _handle(lambda: admin_activity_dynamics(session, limit))


@router.get("", response_model=list[ActivityListItem])
async def list_activities(session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_list_activities(session))


@router.post("", response_model=ActivityDetail, status_code=201)
async def create_activity(payload: ActivityCreate, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_create_activity(session, payload))


@router.get("/{activity_id}", response_model=ActivityDetail)
async def get_activity(activity_id: UUID, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_get_activity(session, activity_id))


@router.patch("/{activity_id}", response_model=ActivityDetail)
async def update_activity(activity_id: UUID, payload: ActivityUpdate, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_update_activity(session, activity_id, payload))


@router.post("/{activity_id}/publish", response_model=ActivityDetail)
async def publish_activity(activity_id: UUID, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_publish_activity(session, activity_id))


@router.post("/{activity_id}/cancel", response_model=ActivityDetail)
async def cancel_activity(activity_id: UUID, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_cancel_activity(session, activity_id))


@router.post("/{activity_id}/finish", response_model=ActivityDetail)
async def finish_activity(activity_id: UUID, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_finish_activity(session, activity_id))


@router.get("/{activity_id}/participants", response_model=list[ParticipantItem])
async def activity_participants(activity_id: UUID, session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    return await _handle(lambda: admin_list_participants(session, activity_id))
