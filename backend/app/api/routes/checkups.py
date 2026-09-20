"""Admin checkup management API (JWT + RBAC: admin roles only)."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db
from backend.app.exceptions import ValidationError
from backend.app.models import HealthCheckReport, User
from backend.app.schemas.checkup import CheckupDetail, CheckupListItem, CheckupStats, CheckupSummary, IndicatorReviewOut, ReviewRequest
from backend.app.services.checkup_service import CheckupManagementService
from backend.app.services.health_report_service import parse_report_background

router = APIRouter(prefix="/checkups", tags=["admin-checkups"])
admin = require_role("admin", "company_admin", "system_admin")


@router.get("/summary", response_model=CheckupSummary)
async def checkup_summary(
    period: str = Query(default="30d", pattern="^(7d|30d|90d)$"),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    return await CheckupManagementService(session).summary(period)


@router.get("", response_model=list[CheckupListItem])
async def list_checkups(
    period: str = Query(default="30d", pattern="^(7d|30d|90d)$"),
    department: str | None = Query(default=None),
    status: str | None = Query(default=None),
    method: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    items = await CheckupManagementService(session).list_reports(period=period, department=department, status=status, method=method)
    if status:
        items = [item for item in items if item["display_status"] == status or item["parse_status"] == status]
    return items


@router.get("/{report_id}", response_model=CheckupDetail)
async def checkup_detail(
    report_id: UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    return await CheckupManagementService(session).get_detail(report_id)


@router.post("/{report_id}/reparse", response_model=CheckupDetail)
async def reparse_checkup(
    report_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(admin),
):
    """Re-run the existing parse pipeline on the original file (no re-upload)."""
    report = await session.get(HealthCheckReport, report_id)
    if report is None:
        raise HTTPException(404, "体检报告不存在")
    if report.parse_status == "parsing":
        raise HTTPException(400, "该报告正在解析中")
    report.parse_status = "uploaded"
    report.parse_progress = 5
    report.parse_error = None
    report.parsed_at = None
    await session.commit()
    await session.refresh(report)
    background_tasks.add_task(parse_report_background, report.id)
    return await CheckupManagementService(session).get_detail(report_id)


@router.patch("/indicators/{indicator_id}/review", response_model=IndicatorReviewOut)
async def review_checkup_indicator(
    indicator_id: UUID,
    payload: ReviewRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin),
):
    service = CheckupManagementService(session)
    try:
        indicator = await service.review_indicator(
            indicator_id, current_user.id,
            action=payload.action,
            reviewed_value=payload.reviewed_value,
            note=payload.note,
        )
        return IndicatorReviewOut(
            id=indicator.id, item_name=indicator.item_name, value=float(indicator.value),
            value_text=indicator.value_text, unit=indicator.unit,
            reference_text=indicator.reference_text, flag=indicator.flag,
            source_type=indicator.source_type,
            confidence=float(indicator.confidence) if indicator.confidence is not None else None,
            review_status=indicator.review_status,
            reviewed_value=float(indicator.reviewed_value) if indicator.reviewed_value is not None else None,
            review_note=indicator.review_note,
        )
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
