"""Authenticated notifications and notification-preferences APIs.

Employees may only read/mark their own notifications and preferences; the
user id always comes from the JWT, never from the request body.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.exceptions import ForbiddenError, NotFoundError
from backend.app.schemas.notifications import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
    UnreadCountResponse,
)
from backend.app.services.notification_service import (
    get_preferences,
    get_unread_count,
    list_notifications,
    mark_all_read,
    mark_read,
    update_preferences,
)

router = APIRouter(tags=["notifications"])


def _notification_to_response(notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        content=notification.content,
        is_read=notification.is_read,
        target_path=notification.target_path,
        created_at=notification.created_at,
    )


async def _handle(fn):
    try:
        return await fn()
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/notifications", response_model=list[NotificationResponse])
async def notifications(limit: int = Query(default=20, ge=1, le=50), current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return [_notification_to_response(item) for item in await list_notifications(session, current_user.id, limit)]
    return await _handle(action)


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def unread_count(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return {"unread_count": await get_unread_count(session, current_user.id)}
    return await _handle(action)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def read_notification(notification_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return _notification_to_response(await mark_read(session, current_user.id, notification_id))
    return await _handle(action)


@router.post("/notifications/read-all", response_model=UnreadCountResponse)
async def read_all(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        await mark_all_read(session, current_user.id)
        return {"unread_count": 0}
    return await _handle(action)


@router.get("/user/notification-preferences", response_model=NotificationPreferencesResponse)
async def notification_preferences(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return NotificationPreferencesResponse(**await get_preferences(session, current_user.id))
    return await _handle(action)


@router.patch("/user/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(payload: NotificationPreferencesUpdate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return NotificationPreferencesResponse(**await update_preferences(session, current_user.id, payload.as_dict))
    return await _handle(action)
