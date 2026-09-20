"""NotificationService: create / list / mark-read / preferences.

All operations are scoped to the JWT user id.  ``create_notification`` checks
the user's per-type preference unless ``force`` is set (used for security
alerts such as authorization denials).  Notification content must be
non-sensitive summaries, never raw health values.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import ForbiddenError, NotFoundError
from backend.app.models import UserNotification, UserPreference
from backend.app.models.notification import NOTIFICATION_TYPES

DEFAULT_PREFERENCES: dict[str, bool] = {
    "system": True,
    "agent_error": True,
    "health_report": True,
    "health_risk": True,
    "health_plan": True,
    "mental_health": True,
    "health_service": True,
    "authorization": True,
}


async def get_preferences(session: AsyncSession, user_id: UUID) -> dict[str, bool]:
    row = await session.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if row is None or not row.notification_preferences:
        return dict(DEFAULT_PREFERENCES)
    merged = dict(DEFAULT_PREFERENCES)
    merged.update({key: bool(value) for key, value in row.notification_preferences.items() if key in DEFAULT_PREFERENCES})
    return merged


async def update_preferences(session: AsyncSession, user_id: UUID, preferences: dict[str, bool]) -> dict[str, bool]:
    allowed = {key: bool(value) for key, value in preferences.items() if key in DEFAULT_PREFERENCES}
    row = await session.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if row is None:
        row = UserPreference(user_id=user_id, notification_preferences=allowed)
        session.add(row)
    else:
        row.notification_preferences = allowed
    await session.commit()
    await session.refresh(row)
    return await get_preferences(session, user_id)


async def create_notification(
    session: AsyncSession,
    user_id: UUID,
    notification_type: str,
    title: str,
    content: str,
    target_path: str | None = None,
    *,
    force: bool = False,
) -> UserNotification | None:
    """Create a notification unless the user disabled this type (or forced)."""
    if notification_type not in NOTIFICATION_TYPES:
        notification_type = "system"
    if not force:
        preferences = await get_preferences(session, user_id)
        if not preferences.get(notification_type, True):
            return None
    notification = UserNotification(
        user_id=user_id,
        type=notification_type,
        title=title,
        content=content,
        is_read=False,
        target_path=target_path,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def list_notifications(session: AsyncSession, user_id: UUID, limit: int = 20) -> list[UserNotification]:
    return list(
        (
            await session.scalars(
                select(UserNotification)
                .where(UserNotification.user_id == user_id)
                .order_by(UserNotification.created_at.desc())
                .limit(limit)
            )
        ).all()
    )


async def get_unread_count(session: AsyncSession, user_id: UUID) -> int:
    return await session.scalar(
        select(func.count(UserNotification.id)).where(UserNotification.user_id == user_id, UserNotification.is_read.is_(False))
    ) or 0


async def mark_read(session: AsyncSession, user_id: UUID, notification_id: UUID) -> UserNotification:
    notification = await session.get(UserNotification, notification_id)
    if notification is None:
        raise NotFoundError("消息不存在")
    if notification.user_id != user_id:
        raise ForbiddenError("无权操作其他员工的消息")
    if not notification.is_read:
        notification.is_read = True
        await session.commit()
        await session.refresh(notification)
    return notification


async def mark_all_read(session: AsyncSession, user_id: UUID) -> int:
    rows = list(
        (
            await session.scalars(
                select(UserNotification).where(UserNotification.user_id == user_id, UserNotification.is_read.is_(False))
            )
        ).all()
    )
    for row in rows:
        row.is_read = True
    if rows:
        await session.commit()
    return len(rows)
