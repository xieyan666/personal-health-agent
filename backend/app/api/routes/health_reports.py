"""Authenticated upload, parse-status and structured-item report APIs."""

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.exceptions import ForbiddenError, NotFoundError, ServiceError, ValidationError
from backend.app.models import HealthCheckReport
from backend.app.schemas.health_reports import HealthCheckReportCreate, HealthCheckReportResponse
from backend.app.schemas.health_report_analysis import HealthReportAnalysisResponse, HealthReportAnalysisTriggerResponse
from backend.app.services.health_report_analysis_service import ReportAnalysisError, get_latest_analysis, trigger_analysis
from backend.app.services.health_report_service import create_report, get_owned_report, is_stale_parse, parse_report_background, report_indicators, serialise_indicator, serialise_report, stream_original_report, upload_original_report

router = APIRouter(prefix="/health-reports", tags=["health-reports"])


async def response_for(session: AsyncSession, report: HealthCheckReport) -> dict:
    return serialise_report(report, await report_indicators(session, report.id))


async def requeue_stale_parse(
    session: AsyncSession, report: HealthCheckReport, background_tasks: BackgroundTasks
) -> HealthCheckReport:
    """Recover a parse abandoned by an API restart without duplicating live work."""
    if not is_stale_parse(report):
        return report
    report.parse_status = "uploaded"
    report.parse_progress = 5
    report.parse_error = None
    await session.commit()
    await session.refresh(report)
    background_tasks.add_task(parse_report_background, report.id)
    return report


@router.get("", response_model=list[HealthCheckReportResponse])
async def list_reports(background_tasks: BackgroundTasks, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    rows = list((await session.scalars(select(HealthCheckReport).where(HealthCheckReport.user_id == current_user.id).order_by(desc(HealthCheckReport.report_date), desc(HealthCheckReport.updated_at)))).all())
    rows = [await requeue_stale_parse(session, row, background_tasks) for row in rows]
    return [await response_for(session, row) for row in rows]


@router.post("", response_model=HealthCheckReportResponse, status_code=status.HTTP_201_CREATED)
async def import_structured_report(payload: HealthCheckReportCreate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Parser/OCR providers may submit verified structured data through this path."""
    return await response_for(session, await create_report(session, current_user.id, payload))


@router.post("/upload", response_model=HealthCheckReportResponse, status_code=status.HTTP_201_CREATED)
async def upload_report(background_tasks: BackgroundTasks, file: UploadFile = File(...), current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        report = await upload_original_report(session, current_user.id, file.filename or "体检报告.pdf", file.content_type, await file.read())
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(503, str(exc)) from exc
    background_tasks.add_task(parse_report_background, report.id)
    return await response_for(session, report)


@router.get("/{report_id}", response_model=HealthCheckReportResponse)
async def get_report(report_id: UUID, background_tasks: BackgroundTasks, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        report = await get_owned_report(session, report_id, current_user.id)
        return await response_for(session, await requeue_stale_parse(session, report, background_tasks))
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{report_id}/parse", response_model=HealthCheckReportResponse)
async def restart_report_parse(report_id: UUID, background_tasks: BackgroundTasks, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Resume an uploaded/failed report after a worker restart or user retry."""
    try:
        report = await get_owned_report(session, report_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    if report.parse_status == "parsing" and not is_stale_parse(report):
        return await response_for(session, report)
    report.parse_status = "uploaded"
    report.parse_progress = 5
    report.parse_error = None
    await session.commit()
    await session.refresh(report)
    background_tasks.add_task(parse_report_background, report.id)
    return await response_for(session, report)


@router.get("/{report_id}/file", response_class=StreamingResponse)
async def view_original_report(report_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Stream the original PDF only to the employee who owns this report."""
    try:
        report = await get_owned_report(session, report_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not report.object_key:
        raise HTTPException(404, "该报告没有可预览的原始 PDF")
    filename = quote(report.file_name or f"{report.report_name}.pdf")
    return StreamingResponse(
        stream_original_report(report.object_key),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}", "Cache-Control": "private, no-store"},
    )


@router.get("/{report_id}/items")
async def get_report_items(report_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    try:
        report = await get_owned_report(session, report_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"report_id": str(report.id), "parse_status": report.parse_status, "parse_progress": report.parse_progress, "parse_error": report.parse_error, "parse_mode": report.parse_mode, "ocr_used": report.ocr_used, "warnings": report.parse_warnings or [], "items": [serialise_indicator(item) for item in await report_indicators(session, report.id)]}


@router.post("/{report_id}/analyze", response_model=HealthReportAnalysisTriggerResponse)
async def analyze_report(report_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Trigger the AI Report Agent interpretation for the report owner.

    The task type is explicit (report_analysis); the Supervisor routes directly
    to the Report Agent without an LLM intent-classification step.  Returns the
    existing completed analysis when the indicator set is unchanged.
    """
    try:
        payload, cached = await trigger_analysis(session, current_user.id, report_id)
    except ReportAnalysisError as exc:
        raise HTTPException(409, str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(503, str(exc)) from exc
    return HealthReportAnalysisTriggerResponse(analysis_id=UUID(payload["analysis_id"]), status=payload["status"], cached=cached)


@router.get("/{report_id}/analysis", response_model=HealthReportAnalysisResponse)
async def read_report_analysis(report_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Return the latest persisted analysis without invoking the model."""
    try:
        payload = await get_latest_analysis(session, report_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc
    if payload is None:
        return HealthReportAnalysisResponse(analysis_id=report_id, report_id=report_id, status="pending")
    return HealthReportAnalysisResponse(
        analysis_id=UUID(payload["analysis_id"]),
        report_id=report_id,
        status=payload["status"],
        error_message=payload.get("error_message"),
        analysis=payload.get("analysis"),
        updated_at=payload.get("updated_at"),
        meta=payload.get("meta"),
    )


@router.post("/{report_id}/reanalyze", response_model=HealthReportAnalysisTriggerResponse)
async def reanalyze_report(report_id: UUID, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """Force a fresh AI interpretation regardless of the cached result."""
    try:
        payload, cached = await trigger_analysis(session, current_user.id, report_id, force=True)
    except ReportAnalysisError as exc:
        raise HTTPException(409, str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(503, str(exc)) from exc
    return HealthReportAnalysisTriggerResponse(analysis_id=UUID(payload["analysis_id"]), status=payload["status"], cached=cached)
