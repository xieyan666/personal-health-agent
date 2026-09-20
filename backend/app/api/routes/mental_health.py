"""Authenticated mental wellness APIs: check-ins, trends, workload, assessments."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.schemas.mental_health import (
    MentalAssessmentCreate,
    MentalAssessmentDefinitionResponse,
    MentalAssessmentResponse,
    MentalCheckinCreate,
    MentalCheckinResponse,
    MentalTrendResponse,
    MentalWorkloadResponse,
)
from backend.app.services.mental_health_service import (
    create_assessment,
    get_checkins_since,
    get_today_checkin,
    get_trends,
    get_workload,
    list_recent_assessments,
    upsert_checkin,
)
from backend.app.services.mental_assessment_definitions import get_assessment_definition, list_assessment_definitions
from backend.app.services.mental_assessment_scoring import (
    InvalidAssessmentAnswersError,
    QuestionnaireNotConfiguredError,
)

router = APIRouter(prefix="/mental-health", tags=["mental-health"])


def _checkin_to_response(checkin) -> MentalCheckinResponse:
    return MentalCheckinResponse(
        id=checkin.id,
        checkin_date=checkin.checkin_date,
        mood=checkin.mood,
        stress_level=checkin.stress_level,
        energy_level=checkin.energy_level,
        sleep_feeling=checkin.sleep_feeling,
        stress_sources=list(checkin.stress_sources or []),
        note=checkin.note,
    )


@router.post("/checkins", response_model=MentalCheckinResponse)
async def save_checkin(payload: MentalCheckinCreate, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return _checkin_to_response(await upsert_checkin(session, current_user.id, payload))


@router.get("/checkins/today", response_model=MentalCheckinResponse | None)
async def today_checkin(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    checkin = await get_today_checkin(session, current_user.id)
    return _checkin_to_response(checkin) if checkin is not None else None


@router.get("/trends", response_model=MentalTrendResponse)
async def trends(
    type: str = Query(default="stress", pattern="^(mood|stress|energy)$"),
    days: int = Query(default=30, ge=7, le=90),
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await get_trends(session, current_user.id, type, days)


@router.get("/workload", response_model=MentalWorkloadResponse)
async def workload(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await get_workload(session, current_user.id)


@router.get("/assessments", response_model=list[MentalAssessmentResponse])
async def assessments(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    rows = await list_recent_assessments(session, current_user.id)
    return [
        MentalAssessmentResponse(
            id=row.id,
            assessment_type=row.assessment_type,
            assessment_version=row.assessment_version,
            score=row.score,
            raw_score=row.raw_score,
            percentage_score=row.percentage_score,
            level=row.level,
            needs_follow_up=row.needs_follow_up,
            safety_flag=row.safety_flag,
            safety_reason=row.safety_reason,
            result_summary=row.result_summary,
            completed_at=row.completed_at,
        )
        for row in rows
    ]


@router.get("/assessment-definitions", response_model=list[MentalAssessmentDefinitionResponse])
async def assessment_definitions(current_user=Depends(get_current_user)):
    """Return only versioned, server-owned questionnaire definitions."""
    return list_assessment_definitions()


@router.get("/assessment-definitions/{assessment_type}", response_model=MentalAssessmentDefinitionResponse)
async def assessment_definition(assessment_type: str, current_user=Depends(get_current_user)):
    try:
        return get_assessment_definition(assessment_type)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="未找到该心理自评量表") from error


@router.post("/assessments", response_model=MentalAssessmentResponse, status_code=201)
async def submit_assessment(
    payload: MentalAssessmentCreate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        row = await create_assessment(session, current_user.id, payload)
    except QuestionnaireNotConfiguredError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "message": "该量表尚未配置经确认的正式题目与评分规则，暂不可开始测评。"},
        ) from error
    except (InvalidAssessmentAnswersError, LookupError, KeyError) as error:
        raise HTTPException(status_code=422, detail={"code": getattr(error, "code", "ASSESSMENT_INVALID"), "message": "测评答案或量表版本无效。"}) from error
    return MentalAssessmentResponse(
        id=row.id,
        assessment_type=row.assessment_type,
        assessment_version=row.assessment_version,
        score=row.score,
        raw_score=row.raw_score,
        percentage_score=row.percentage_score,
        level=row.level,
        needs_follow_up=row.needs_follow_up,
        safety_flag=row.safety_flag,
        safety_reason=row.safety_reason,
        result_summary=row.result_summary,
        completed_at=row.completed_at,
    )


@router.get("/trend-context")
async def trend_context(current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    """MentalHealthTrendTool payload for the AI assistant (read-only)."""
    from backend.app.tools.mental_health_trend import get_mental_health_trend_context
    return await get_mental_health_trend_context(session, current_user.id)
