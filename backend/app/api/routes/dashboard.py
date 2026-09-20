"""A lightweight, read-only employee health workspace aggregation endpoint.

The dashboard deliberately consumes persisted business results only.  It does
not invoke an LLM, recompute risk, parse reports, or alter any user data.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.models import (
    HealthCheckReport,
    HealthPlan,
    HealthPlanTask,
    HealthReportAnalysis,
    HealthRiskScore,
    HealthServiceBooking,
    MentalCheckin,
    RiskAssessment,
    UserNotification,
)
from backend.app.schemas.dashboard import (
    DashboardActivePlan,
    DashboardActivity,
    DashboardHealthOverview,
    DashboardMentalToday,
    DashboardRecommendation,
    DashboardRiskSummary,
    DashboardSummaryResponse,
    DashboardTask,
)
from backend.app.services.health_plan_service import compute_plan_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _risk_status(level: str) -> str:
    normalized = (level or "").lower()
    if normalized in {"high", "风险较高", "高风险"}:
        return "high"
    if normalized in {"medium", "attention", "需关注", "需要关注"}:
        return "attention"
    return "normal"


def _overview_label(score: int | None, risk_status: str, has_assessment: bool) -> str:
    if score is not None:
        return "良好" if score >= 90 else "稳定" if score >= 75 else "需要关注" if score >= 60 else "风险较高"
    if not has_assessment:
        return "暂无评估"
    return {"normal": "良好", "attention": "需要关注", "high": "风险较高"}[risk_status]


def _activity_time(row) -> datetime:
    return row.created_at or datetime.combine(date.today(), time.min, tzinfo=timezone.utc)


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return the current employee's persisted overview, without recalculation."""
    user_id = current_user.id
    today = date.today()

    # Health risk state: only stored rule-engine rows are read here.
    latest_score = await session.scalar(
        select(HealthRiskScore)
        .where(HealthRiskScore.user_id == user_id)
        .order_by(desc(HealthRiskScore.period_end), desc(HealthRiskScore.created_at))
        .limit(1)
    )
    latest_risk_at = await session.scalar(
        select(RiskAssessment.assessed_at)
        .where(RiskAssessment.user_id == user_id)
        .order_by(desc(RiskAssessment.assessed_at))
        .limit(1)
    )
    risk_rows = []
    if latest_risk_at is not None:
        risk_rows = list((await session.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.user_id == user_id, RiskAssessment.assessed_at == latest_risk_at)
            .order_by(RiskAssessment.risk_type)
        )).all())
    attention_rows = [row for row in risk_rows if _risk_status(row.level) != "normal"]
    severity = "high" if any(_risk_status(row.level) == "high" for row in attention_rows) else "attention" if attention_rows else "normal"
    primary_risk = attention_rows[0] if attention_rows else None
    health_score = latest_score.risk_score if latest_score is not None else None
    health_overview = DashboardHealthOverview(
        label=_overview_label(health_score, severity, bool(risk_rows or latest_score)),
        score=health_score,
        assessed_at=latest_score.updated_at if latest_score is not None else latest_risk_at,
    )
    risk_summary = DashboardRiskSummary(
        attention_count=len(attention_rows),
        primary_factor=(primary_risk.description if primary_risk else None),
        status="empty" if not risk_rows and latest_score is None else severity,
    )

    # Plan and tasks remain direct projections of the existing plan entities.
    plan = await session.scalar(
        select(HealthPlan)
        .where(HealthPlan.user_id == user_id, HealthPlan.status == "active")
        .order_by(desc(HealthPlan.updated_at))
        .limit(1)
    )
    plan_tasks: list[HealthPlanTask] = []
    active_plan = DashboardActivePlan()
    if plan is not None:
        plan_tasks = list((await session.scalars(
            select(HealthPlanTask)
            .where(HealthPlanTask.user_id == user_id, HealthPlanTask.plan_id == plan.id)
            .order_by(HealthPlanTask.day_index, HealthPlanTask.created_at)
        )).all())
        stats = compute_plan_stats(plan_tasks, plan.duration_days)
        current_day = min(max((today - plan.start_date).days + 1, 1), max(plan.duration_days, 1))
        active_plan = DashboardActivePlan(
            id=str(plan.id), name=plan.plan_name, current_day=current_day,
            duration_days=plan.duration_days, completion_rate=stats["task_completion_rate"], status=plan.status,
        )

    checkin = await session.scalar(
        select(MentalCheckin).where(MentalCheckin.user_id == user_id, MentalCheckin.checkin_date == today)
    )
    mental_today = DashboardMentalToday(
        checked_in=checkin is not None,
        mood=checkin.mood if checkin is not None else None,
        stress_level=checkin.stress_level if checkin is not None else None,
    )

    latest_report = await session.scalar(
        select(HealthCheckReport)
        .where(HealthCheckReport.user_id == user_id)
        .order_by(desc(HealthCheckReport.report_date), desc(HealthCheckReport.updated_at))
        .limit(1)
    )
    latest_analysis = None
    if latest_report is not None:
        latest_analysis = await session.scalar(
            select(HealthReportAnalysis)
            .where(HealthReportAnalysis.user_id == user_id, HealthReportAnalysis.report_id == latest_report.id)
            .order_by(desc(HealthReportAnalysis.updated_at))
            .limit(1)
        )

    recommendations: list[DashboardRecommendation] = []
    if primary_risk is not None:
        recommendations.append(DashboardRecommendation(
            id=f"risk-{primary_risk.id}", title="优先关注近期健康风险",
            description=primary_risk.recommendation or primary_risk.description,
            source="健康风险分析", target_path="/employee/risk",
            tone="attention" if severity != "normal" else "normal",
        ))
    if latest_analysis is not None and latest_analysis.analysis_status == "completed":
        recommendations.append(DashboardRecommendation(
            id=f"report-{latest_analysis.id}", title="查看最新体检解读",
            description="最新体检报告已完成结构化分析，可查看重点指标与健康建议。",
            source="AI 体检解读", target_path="/employee/reports", tone="info",
        ))
    if plan is not None:
        recommendations.append(DashboardRecommendation(
            id=f"plan-{plan.id}", title="继续执行当前健康计划",
            description=f"“{plan.plan_name}”正在执行中，完成今天的任务可持续积累健康习惯。",
            source="健康计划", target_path="/employee/plan", tone="normal",
        ))
    if checkin is None:
        recommendations.append(DashboardRecommendation(
            id="mental-checkin", title="完成今日心理状态打卡",
            description="记录今天的情绪、压力和精力状态，帮助你持续了解自身变化。",
            source="心理健康", target_path="/employee/mental", tone="info",
        ))
    if not recommendations:
        recommendations.append(DashboardRecommendation(
            id="profile", title="完善健康档案", description="完善基础健康信息后，系统可以提供更完整的个人健康概览。",
            source="健康档案", target_path="/employee/profile", tone="info",
        ))

    today_plan_tasks = [task for task in plan_tasks if task.task_date == today]
    if not today_plan_tasks and plan is not None:
        today_plan_tasks = [task for task in plan_tasks if task.day_index == active_plan.current_day]
    today_tasks = [
        DashboardTask(
            id=f"plan-task-{task.id}", title=task.title, source=plan.plan_name if plan else "健康计划",
            target_path="/employee/plan", status="completed" if task.completion_status == "completed" else "pending",
            detail=task.target_value or task.description,
        )
        for task in today_plan_tasks[:5]
    ]
    if checkin is None and len(today_tasks) < 5:
        today_tasks.append(DashboardTask(
            id="mental-checkin", title="完成心理状态打卡", source="心理健康",
            target_path="/employee/mental", status="pending", detail="记录今天的情绪、压力与精力状态",
        ))
    today_bookings = list((await session.scalars(
        select(HealthServiceBooking)
        .where(
            HealthServiceBooking.user_id == user_id,
            HealthServiceBooking.booking_date == today,
            HealthServiceBooking.status.in_(("pending", "confirmed", "in_progress", "completed")),
        )
        .order_by(HealthServiceBooking.booking_time)
    )).all())
    for booking in today_bookings:
        if len(today_tasks) >= 5:
            break
        today_tasks.append(DashboardTask(
            id=f"booking-{booking.id}", title="查看今日健康服务预约", source="健康服务",
            target_path="/employee/services", status="completed" if booking.status == "completed" else "pending",
            detail=f"预约时间 {booking.booking_time}",
        ))
    if latest_analysis is not None and latest_analysis.analysis_status == "completed" and len(today_tasks) < 5:
        today_tasks.append(DashboardTask(
            id=f"report-analysis-{latest_analysis.id}", title="查看最新 AI 体检解读", source="体检报告",
            target_path="/employee/reports", status="completed" if latest_analysis.updated_at.date() < today else "pending",
            detail="查看本次报告的结构化指标与健康建议",
        ))

    notifications = list((await session.scalars(
        select(UserNotification)
        .where(UserNotification.user_id == user_id)
        .order_by(desc(UserNotification.created_at))
        .limit(5)
    )).all())
    recent_activities = [DashboardActivity(
        id=f"notification-{row.id}", title=row.title, occurred_at=_activity_time(row),
        target_path=row.target_path, kind=row.type,
    ) for row in notifications]
    if not recent_activities:
        # Fallback timestamps are still user-owned persisted business events.
        fallback = []
        if checkin is not None:
            fallback.append(DashboardActivity(id=f"checkin-{checkin.id}", title="完成心理状态打卡", occurred_at=_activity_time(checkin), target_path="/employee/mental", kind="mental_health"))
        if plan is not None:
            fallback.append(DashboardActivity(id=f"plan-{plan.id}", title="健康计划已更新", occurred_at=_activity_time(plan), target_path="/employee/plan", kind="health_plan"))
        if latest_report is not None:
            fallback.append(DashboardActivity(id=f"report-{latest_report.id}", title="体检报告已上传", occurred_at=_activity_time(latest_report), target_path="/employee/reports", kind="health_report"))
        recent_activities = sorted(fallback, key=lambda item: item.occurred_at, reverse=True)[:5]

    return DashboardSummaryResponse(
        health_overview=health_overview, risk_summary=risk_summary, active_plan=active_plan,
        mental_today=mental_today, recommendations=recommendations[:3], today_tasks=today_tasks[:5],
        recent_activities=recent_activities,
    )
