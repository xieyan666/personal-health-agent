"""Authenticated health services APIs: catalog, recommendations, activities,
bookings and benefits."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.app.schemas.health_services import (
    BookingCreate,
    EmployeeHealthBenefitResponse,
    HealthActivityResponse,
    HealthServiceBookingResponse,
    HealthServiceResponse,
    ServiceRecommendationListResponse,
)
from backend.app.services.health_recommendation_service import get_service_recommendations
from backend.app.services.health_service_service import (
    cancel_booking,
    create_booking,
    get_service,
    list_benefits,
    list_bookings,
    list_services,
)
from backend.app.services.health_activity_service import (
    cancel_activity_registration,
    get_activity_detail,
    join_activity,
    list_available_activities,
    list_my_activities,
)
from backend.app.models import AgentApproval
from backend.app.services.data_authorization_service import AuthorizationService, DataAccessNotAuthorized

router = APIRouter(tags=["health-services"])


def _service_to_response(service) -> HealthServiceResponse:
    return HealthServiceResponse(
        id=service.id,
        name=service.name,
        category=service.category,
        description=service.description,
        duration_minutes=service.duration_minutes,
        delivery_mode=service.delivery_mode,
        suitability=service.suitability,
        is_annual_check=service.is_annual_check,
    )


async def _handle(fn):
    try:
        return await fn()
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/health-services", response_model=list[HealthServiceResponse])
async def services(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return [_service_to_response(service) for service in await list_services(session)]
    return await _handle(action)


@router.get("/health-services/recommendations", response_model=ServiceRecommendationListResponse)
async def service_recommendations(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await get_service_recommendations(session, current_user.id)
    return await _handle(action)


@router.get("/health-activities", response_model=list[dict])
async def activities(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await list_available_activities(session, current_user)
    return await _handle(action)


@router.get("/health-activities/{activity_id}", response_model=dict)
async def activity_detail(activity_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await get_activity_detail(session, current_user, activity_id)
    return await _handle(action)


@router.post("/health-activities/{activity_id}/join", response_model=dict)
async def join_activity_endpoint(activity_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await join_activity(session, current_user, activity_id)
    return await _handle(action)


@router.post("/health-activities/{activity_id}/cancel", response_model=dict)
async def cancel_activity_endpoint(activity_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await cancel_activity_registration(session, current_user, activity_id)
    return await _handle(action)


@router.get("/my-health-activities", response_model=list[dict])
async def my_activities(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await list_my_activities(session, current_user)
    return await _handle(action)


@router.get("/health-service-bookings", response_model=list[HealthServiceBookingResponse])
async def bookings(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await list_bookings(session, current_user.id)
    return await _handle(action)


@router.post("/health-service-bookings", response_model=HealthServiceBookingResponse, status_code=201)
async def create_booking_endpoint(payload: BookingCreate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        authorization = AuthorizationService(session)
        service = await get_service(session, payload.service_id)
        required_scopes = ["health_profile.read", "health_service.booking.create"]
        if service.category in {"nutrition", "medical_consult"}:
            required_scopes.insert(1, "health_plan.read")
        try:
            for scope in required_scopes:
                await authorization.require(user_id=current_user.id, grantee_type="agent", grantee_id="health_service_agent", scope=scope, purpose=f"用于健康服务预约：{service.name}")
        except DataAccessNotAuthorized as exc:
            raise ForbiddenError(f"需要先在数据授权页面授权：{exc.scope}") from exc
        if payload.approval_id is None:
            raise ConflictError("预约属于高风险操作，请先确认授权并完成预约确认")
        approval = await session.get(AgentApproval, payload.approval_id)
        if approval is None or approval.user_id != current_user.id or approval.status != "approved" or approval.action_type != "health_service.booking.create":
            raise ForbiddenError("预约确认无效或已失效")
        return await create_booking(session, current_user.id, payload.service_id, payload.booking_date, payload.booking_time)
    return await _handle(action)


@router.patch("/health-service-bookings/{booking_id}/cancel", response_model=HealthServiceBookingResponse)
async def cancel_booking_endpoint(booking_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await cancel_booking(session, current_user.id, booking_id)
    return await _handle(action)


@router.get("/health-benefits", response_model=list[EmployeeHealthBenefitResponse])
async def benefits(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def action():
        return await list_benefits(session, current_user.id)
    return await _handle(action)
