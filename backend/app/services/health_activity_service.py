"""Enterprise health-activity operations.

Admin side: create / edit / publish / cancel / finish activities and inspect
registrations.  Employee side: browse published activities in scope, join,
soft-cancel, and list personal registrations.  All write decisions (eligibility,
capacity, duplicates) are enforced server-side from the JWT user; the frontend
never decides final capacity.

Cancel keeps the row: ``HealthActivityParticipant.status`` flips to
``cancelled`` so registration history is preserved.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.app.models import HealthActivity, HealthActivityParticipant, User
from backend.app.services.notification_service import create_notification

ACTIVITY_TYPES = ("lecture", "exercise", "nutrition", "education", "exam_promo", "other")
ACTIVITY_TYPE_LABELS = {
    "lecture": "健康讲座",
    "exercise": "运动活动",
    "nutrition": "营养课程",
    "education": "健康教育",
    "exam_promo": "体检宣教",
    "other": "其他",
}
ACTIVITY_STATUSES = ("draft", "registration_open", "registration_closed", "ongoing", "finished", "cancelled")
ACTIVITY_STATUS_LABELS = {
    "draft": "草稿",
    "registration_open": "报名中",
    "registration_closed": "报名截止",
    "ongoing": "进行中",
    "finished": "已结束",
    "cancelled": "已取消",
    "active": "进行中",
}
DELIVERY_MODES = ("online", "offline")

# Allowed status transitions driven by admin actions.
PUBLISHABLE_STATUSES = ("draft", "registration_closed")


def _local_to_utc(day: date, time_str: str | None) -> datetime:
    """Interpret a local (Asia/Shanghai) date+time and return an aware UTC datetime."""
    try:
        from zoneinfo import ZoneInfo
        hour, minute = 0, 0
        if time_str:
            parsed = dt_time.fromisoformat(time_str)
            hour, minute = parsed.hour, parsed.minute
        local = datetime.combine(day, dt_time(hour, minute), tzinfo=ZoneInfo("Asia/Shanghai"))
        return local.astimezone(timezone.utc)
    except Exception:
        return datetime.combine(day, dt_time(), tzinfo=timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_display_status(activity: HealthActivity, now: datetime | None = None) -> str:
    """Auto-advance the stored status using dates/deadline; returns the
    authoritative status the UI and eligibility checks should use."""
    now = now or datetime.now(timezone.utc)
    status = activity.status
    if status in ("draft", "cancelled", "finished"):
        return status
    if status == "registration_open" and activity.registration_deadline is not None:
        if now > _as_utc(activity.registration_deadline):
            status = "registration_closed"
    if status in ("registration_open", "registration_closed") and activity.start_date is not None:
        if now >= _local_to_utc(activity.start_date, activity.start_time):
            status = "ongoing"
    if status == "ongoing" and activity.end_date is not None:
        if now > _local_to_utc(activity.end_date, activity.end_time):
            status = "finished"
    return status


def _remaining(activity: HealthActivity) -> int | None:
    if activity.capacity is None:
        return None
    return max(activity.capacity - activity.participants, 0)


def serialize_activity(activity: HealthActivity, joined: bool = False, display_status: str | None = None) -> dict[str, Any]:
    status = display_status or compute_display_status(activity)
    return {
        "id": activity.id,
        "name": activity.name,
        "activity_type": activity.activity_type,
        "activity_type_label": ACTIVITY_TYPE_LABELS.get(activity.activity_type, activity.activity_type),
        "description": activity.description,
        "start_date": activity.start_date,
        "end_date": activity.end_date,
        "start_time": activity.start_time,
        "end_time": activity.end_time,
        "registration_deadline": activity.registration_deadline,
        "delivery_mode": activity.delivery_mode,
        "location": activity.location,
        "scope": activity.scope,
        "target_department": activity.target_department,
        "organizer": activity.organizer,
        "contact_person": activity.contact_person,
        "capacity": activity.capacity,
        "participants": activity.participants,
        "remaining": _remaining(activity),
        "status": activity.status,
        "display_status": status,
        "display_status_label": ACTIVITY_STATUS_LABELS.get(status, status),
        "joined": joined,
        "created_at": activity.created_at,
    }


async def count_active_participants(session: AsyncSession, activity_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count(HealthActivityParticipant.id)).where(
                HealthActivityParticipant.activity_id == activity_id,
                HealthActivityParticipant.status == "joined",
            )
        )
    ) or 0


def _sync_counter(activity: HealthActivity, count: int) -> None:
    """Keep the denormalized counter in sync with real joined rows."""
    activity.participants = count


# ---------------------------------------------------------------------------
# Employee side
# ---------------------------------------------------------------------------

def _user_in_scope(activity: HealthActivity, user: User) -> bool:
    if activity.scope == "department":
        if not activity.target_department:
            return False
        return (user.department or "") == activity.target_department
    return True


async def list_available_activities(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    rows = list((await session.scalars(select(HealthActivity).order_by(HealthActivity.created_at.desc()))).all())
    joined_ids = set(
        (
            await session.scalars(
                select(HealthActivityParticipant.activity_id).where(
                    HealthActivityParticipant.user_id == user.id,
                    HealthActivityParticipant.status == "joined",
                )
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    for activity in rows:
        display = compute_display_status(activity, now)
        if display not in ("registration_open", "registration_closed", "ongoing"):
            continue
        if not _user_in_scope(activity, user):
            continue
        result.append(serialize_activity(activity, joined=activity.id in joined_ids, display_status=display))
    return result


async def get_activity_detail(session: AsyncSession, user: User, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    display = compute_display_status(activity)
    if display not in ("registration_open", "registration_closed", "ongoing"):
        raise NotFoundError("活动不存在或未开放")
    if not _user_in_scope(activity, user):
        raise ForbiddenError("该活动不在你的参与范围内")
    joined = await session.scalar(
        select(HealthActivityParticipant.id).where(
            HealthActivityParticipant.activity_id == activity_id,
            HealthActivityParticipant.user_id == user.id,
            HealthActivityParticipant.status == "joined",
        )
    ) is not None
    return serialize_activity(activity, joined=joined, display_status=display)


async def join_activity(session: AsyncSession, user: User, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    display = compute_display_status(activity)
    if display != "registration_open":
        raise ValidationError("活动当前不在报名期，无法报名")
    if not _user_in_scope(activity, user):
        raise ForbiddenError("该活动不在你的参与范围内")
    existing = await session.scalar(
        select(HealthActivityParticipant).where(
            HealthActivityParticipant.activity_id == activity_id,
            HealthActivityParticipant.user_id == user.id,
        )
    )
    if existing is not None and existing.status == "joined":
        raise ConflictError("你已报名该活动，请勿重复报名")
    active_count = await count_active_participants(session, activity_id)
    if activity.capacity is not None and active_count >= activity.capacity:
        raise ValidationError("活动名额已满")
    if existing is not None and existing.status == "cancelled":
        existing.status = "joined"
    else:
        session.add(HealthActivityParticipant(activity_id=activity_id, user_id=user.id, status="joined"))
    _sync_counter(activity, active_count + 1)
    await session.commit()
    await session.refresh(activity)
    await create_notification(
        session,
        user.id,
        "health_service",
        "活动报名成功",
        f"你已成功报名「{activity.name}」，请留意活动时间安排。",
        "/employee/services",
    )
    return serialize_activity(activity, joined=True)


async def cancel_activity_registration(session: AsyncSession, user: User, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    existing = await session.scalar(
        select(HealthActivityParticipant).where(
            HealthActivityParticipant.activity_id == activity_id,
            HealthActivityParticipant.user_id == user.id,
        )
    )
    if existing is None or existing.status != "joined":
        raise ConflictError("你尚未报名该活动")
    display = compute_display_status(activity)
    if display in ("finished", "cancelled"):
        raise ValidationError("活动已结束或已取消，无法取消报名")
    existing.status = "cancelled"
    # autoflush=False on the shared session factory: the count below must see
    # the pending status change, so flush explicitly first.
    await session.flush()
    active_count = await count_active_participants(session, activity_id)
    _sync_counter(activity, active_count)
    await session.commit()
    await session.refresh(activity)
    return serialize_activity(activity, joined=False)


async def list_my_activities(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(HealthActivityParticipant)
                .where(HealthActivityParticipant.user_id == user.id)
                .order_by(HealthActivityParticipant.created_at.desc())
            )
        ).all()
    )
    activities = {activity.id: activity for activity in (await session.scalars(select(HealthActivity))).all()}
    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    for row in rows:
        activity = activities.get(row.activity_id)
        if activity is None:
            continue
        display = compute_display_status(activity, now)
        if row.status == "cancelled":
            group = "cancelled"
        elif display == "finished":
            group = "finished"
        else:
            group = "upcoming"
        result.append({
            "id": row.id,
            "activity_id": activity.id,
            "group": group,
            "status": row.status,
            "activity": serialize_activity(activity, joined=row.status == "joined", display_status=display),
            "joined_at": row.created_at,
        })
    return result


# ---------------------------------------------------------------------------
# Admin side
# ---------------------------------------------------------------------------

async def admin_list_activities(session: AsyncSession) -> list[dict[str, Any]]:
    rows = list((await session.scalars(select(HealthActivity).order_by(HealthActivity.created_at.desc()))).all())
    now = datetime.now(timezone.utc)
    return [serialize_activity(activity, display_status=compute_display_status(activity, now)) for activity in rows]


async def admin_get_activity(session: AsyncSession, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    return serialize_activity(activity)


async def admin_create_activity(session: AsyncSession, payload: Any) -> dict[str, Any]:
    activity = HealthActivity(
        name=payload.name,
        activity_type=payload.activity_type,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        registration_deadline=payload.registration_deadline,
        delivery_mode=payload.delivery_mode,
        location=payload.location,
        scope=payload.scope,
        target_department=payload.target_department,
        organizer=payload.organizer,
        contact_person=payload.contact_person,
        capacity=payload.capacity,
        participants=0,
        status="draft",
    )
    session.add(activity)
    await session.commit()
    await session.refresh(activity)
    return serialize_activity(activity)


async def admin_update_activity(session: AsyncSession, activity_id: UUID, payload: Any) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    if activity.status not in ("draft", "registration_closed"):
        raise ValidationError("仅草稿或报名截止状态的活动可以编辑")
    for field in (
        "name", "activity_type", "description", "start_date", "end_date", "start_time", "end_time",
        "registration_deadline", "delivery_mode", "location", "scope", "target_department",
        "organizer", "contact_person", "capacity",
    ):
        setattr(activity, field, getattr(payload, field))
    await session.commit()
    await session.refresh(activity)
    return serialize_activity(activity)


async def admin_publish_activity(session: AsyncSession, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    if activity.status not in PUBLISHABLE_STATUSES:
        raise ValidationError("仅草稿或报名截止的活动可以发布")
    if activity.registration_deadline is None and activity.start_date is not None:
        activity.registration_deadline = _local_to_utc(activity.start_date, activity.start_time)
    activity.status = "registration_open"
    await session.commit()
    await session.refresh(activity)
    await _notify_eligible_employees(session, activity, "新活动发布", f"新活动「{activity.name}」已开放报名，欢迎报名参加。")
    return serialize_activity(activity)


async def admin_cancel_activity(session: AsyncSession, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    if activity.status == "cancelled":
        raise ConflictError("活动已取消")
    if activity.status == "finished":
        raise ValidationError("已结束的活动不能取消")
    activity.status = "cancelled"
    await session.commit()
    await session.refresh(activity)
    return serialize_activity(activity)


async def admin_finish_activity(session: AsyncSession, activity_id: UUID) -> dict[str, Any]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    if activity.status in ("finished", "cancelled", "draft"):
        raise ValidationError("当前状态不能结束活动")
    activity.status = "finished"
    await session.commit()
    await session.refresh(activity)
    return serialize_activity(activity)


async def admin_list_participants(session: AsyncSession, activity_id: UUID) -> list[dict[str, Any]]:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None:
        raise NotFoundError("活动不存在")
    rows = list(
        (
            await session.scalars(
                select(HealthActivityParticipant)
                .where(HealthActivityParticipant.activity_id == activity_id)
                .order_by(HealthActivityParticipant.created_at.desc())
            )
        ).all()
    )
    users = {user.id: user for user in (await session.scalars(select(User))).all()}
    result: list[dict[str, Any]] = []
    for row in rows:
        user = users.get(row.user_id)
        if user is None:
            continue
        result.append({
            "id": row.id,
            "user_id": row.user_id,
            "employee_no": user.username,
            "employee_name": user.display_name or user.username,
            "department": user.department,
            "joined_at": row.created_at,
            "status": row.status,
        })
    return result


async def admin_summary(session: AsyncSession) -> dict[str, int | float]:
    now = datetime.now(timezone.utc)
    rows = list((await session.scalars(select(HealthActivity))).all())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_count = 0
    open_count = 0
    total_participants = 0
    rates: list[float] = []
    for activity in rows:
        created_at = _as_utc(activity.created_at) or now
        if created_at >= month_start and activity.status != "cancelled":
            month_count += 1
        display = compute_display_status(activity, now)
        if display == "registration_open":
            open_count += 1
        if activity.status != "cancelled":
            total_participants += activity.participants
        if activity.capacity and activity.capacity > 0 and activity.participants >= 0:
            rates.append(min(activity.participants / activity.capacity, 1.0))
    avg_rate = round(sum(rates) / len(rates) * 100, 1) if rates else 0.0
    return {
        "month_activity_count": month_count,
        "open_registration_count": open_count,
        "total_participants": total_participants,
        "avg_participation_rate": avg_rate,
    }


async def admin_activity_dynamics(session: AsyncSession, limit: int = 12) -> list[dict[str, Any]]:
    """Recent registration events (joined / cancelled) for the ops feed.

    Reads the participant rows (which are soft-cancelled, never deleted), so
    the feed shows the latest state per participant with its occurrence time.
    """
    rows = list(
        (
            await session.scalars(
                select(HealthActivityParticipant)
                .order_by(HealthActivityParticipant.updated_at.desc())
                .limit(min(max(limit, 1), 50))
            )
        ).all()
    )
    activities = {activity.id: activity for activity in (await session.scalars(select(HealthActivity))).all()}
    users = {user.id: user for user in (await session.scalars(select(User))).all()}
    result: list[dict[str, Any]] = []
    for row in rows:
        activity = activities.get(row.activity_id)
        user = users.get(row.user_id)
        if activity is None:
            continue
        result.append({
            "id": row.id,
            "activity_id": row.activity_id,
            "activity_name": activity.name,
            "department": user.department if user else None,
            "employee_name": user.display_name if user else None,
            "action": "joined" if row.status == "joined" else "cancelled",
            "occurred_at": row.updated_at,
        })
    return result


async def _notify_eligible_employees(session: AsyncSession, activity: HealthActivity, title: str, content: str) -> None:
    """Notify every employee inside the activity scope (non-sensitive content only)."""
    query = select(User.id).where(User.role == "employee", User.status == "active")
    if activity.scope == "department" and activity.target_department:
        query = query.where(User.department == activity.target_department)
    user_ids = list((await session.scalars(query)).all())
    for user_id in user_ids:
        await create_notification(
            session,
            user_id,
            "health_service",
            title,
            content,
            "/employee/services",
        )
