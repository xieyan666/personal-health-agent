"""Health services business operations: catalog, activities, bookings and benefits."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.app.models import (
    EmployeeHealthBenefit,
    HealthActivity,
    HealthActivityParticipant,
    HealthService,
    HealthServiceBooking,
)
from backend.app.services.notification_service import create_notification

BOOKING_STATUSES = {"pending", "confirmed", "in_progress", "completed", "cancelled"}


async def list_services(session: AsyncSession) -> list[HealthService]:
    return list(
        (
            await session.scalars(
                select(HealthService)
                .where(HealthService.status == "active")
                .order_by(HealthService.sort_order, HealthService.name)
            )
        ).all()
    )


async def get_service(session: AsyncSession, service_id: UUID) -> HealthService:
    service = await session.get(HealthService, service_id)
    if service is None or service.status != "active":
        raise NotFoundError("健康服务不存在")
    return service


async def list_activities(session: AsyncSession, user_id: UUID) -> list[dict]:
    rows = list((await session.scalars(select(HealthActivity).where(HealthActivity.status == "active").order_by(HealthActivity.created_at))).all())
    joined_ids = set(
        (
            await session.scalars(
                select(HealthActivityParticipant.activity_id).where(HealthActivityParticipant.user_id == user_id)
            )
        ).all()
    )
    result = []
    for activity in rows:
        remaining = None
        if activity.capacity is not None:
            remaining = max(activity.capacity - activity.participants, 0)
        result.append({
            "id": activity.id,
            "name": activity.name,
            "activity_type": activity.activity_type,
            "description": activity.description,
            "start_date": activity.start_date,
            "end_date": activity.end_date,
            "schedule": activity.schedule,
            "duration_minutes": activity.duration_minutes,
            "capacity": activity.capacity,
            "participants": activity.participants,
            "remaining": remaining,
            "joined": activity.id in joined_ids,
        })
    return result


async def join_activity(session: AsyncSession, user_id: UUID, activity_id: UUID) -> dict:
    activity = await session.get(HealthActivity, activity_id)
    if activity is None or activity.status != "active":
        raise NotFoundError("企业健康活动不存在或已结束")
    existing = await session.scalar(
        select(HealthActivityParticipant).where(
            HealthActivityParticipant.activity_id == activity_id,
            HealthActivityParticipant.user_id == user_id,
        )
    )
    if existing is not None:
        raise ConflictError("已报名该活动")
    if activity.capacity is not None and activity.participants >= activity.capacity:
        raise ValidationError("活动名额已满")
    activity.participants += 1
    session.add(HealthActivityParticipant(activity_id=activity_id, user_id=user_id))
    await session.commit()
    remaining = None
    if activity.capacity is not None:
        remaining = max(activity.capacity - activity.participants, 0)
    return {
        "id": activity.id,
        "name": activity.name,
        "participants": activity.participants,
        "remaining": remaining,
        "joined": True,
    }


async def list_bookings(session: AsyncSession, user_id: UUID) -> list[dict]:
    rows = list(
        (
            await session.scalars(
                select(HealthServiceBooking)
                .where(HealthServiceBooking.user_id == user_id)
                .order_by(HealthServiceBooking.booking_date.desc(), HealthServiceBooking.booking_time.desc())
            )
        ).all()
    )
    service_names = {service.id: service for service in await list_services(session)}
    result = []
    for booking in rows:
        service = service_names.get(booking.service_id)
        result.append({
            "id": booking.id,
            "service_id": booking.service_id,
            "service_name": service.name if service else "未知服务",
            "category": service.category if service else "",
            "booking_date": booking.booking_date,
            "booking_time": booking.booking_time,
            "status": booking.status,
            "provider": booking.provider,
        })
    return result


async def create_booking(session: AsyncSession, user_id: UUID, service_id: UUID, booking_date: date, booking_time: str) -> dict:
    service = await get_service(session, service_id)
    booking = HealthServiceBooking(
        user_id=user_id,
        service_id=service_id,
        booking_date=booking_date,
        booking_time=booking_time,
        status="pending",
        provider=None,
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)
    await create_notification(
        session,
        user_id,
        "health_service",
        "健康服务预约成功",
        f"你的健康服务预约「{service.name}」已提交，等待确认。",
        "/employee/services",
    )
    return {
        "id": booking.id,
        "service_id": service_id,
        "service_name": service.name,
        "category": service.category,
        "booking_date": booking_date,
        "booking_time": booking_time,
        "status": "pending",
        "provider": None,
    }


async def cancel_booking(session: AsyncSession, user_id: UUID, booking_id: UUID) -> dict:
    booking = await session.get(HealthServiceBooking, booking_id)
    if booking is None:
        raise NotFoundError("预约不存在")
    if booking.user_id != user_id:
        raise ForbiddenError("无权操作其他员工的预约")
    if booking.status in ("completed", "cancelled"):
        raise ConflictError("该预约已完成或已取消")
    booking.status = "cancelled"
    await session.commit()
    await session.refresh(booking)
    service_names = {service.id: service for service in await list_services(session)}
    service = service_names.get(booking.service_id)
    return {
        "id": booking.id,
        "service_id": booking.service_id,
        "service_name": service.name if service else "未知服务",
        "category": service.category if service else "",
        "booking_date": booking.booking_date,
        "booking_time": booking.booking_time,
        "status": booking.status,
        "provider": booking.provider,
    }


async def list_benefits(session: AsyncSession, user_id: UUID) -> list[dict]:
    rows = list(
        (
            await session.scalars(
                select(EmployeeHealthBenefit).where(EmployeeHealthBenefit.user_id == user_id).order_by(EmployeeHealthBenefit.id)
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "benefit_type": row.benefit_type,
            "benefit_name": row.benefit_name,
            "annual_quota": row.annual_quota,
            "used_quota": row.used_quota,
            "remaining_quota": max(row.annual_quota - row.used_quota, 0),
        }
        for row in rows
    ]
