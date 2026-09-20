"""ServiceRecommendationTool: rule-based candidate matching from real data.

The tool is deliberately LLM-free.  It reads the current employee's health
profile, risk assessments, latest parsed health report + AI analysis, active
health plan, and the live service catalog, then emits candidate
recommendations with structured evidence.  Matching rules decide; the AI
interpreter (Health Supervisor stage) only rewrites the evidence into natural
language later — it never re-judges high/low or fabricates services.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import (
    HealthCheckIndicator,
    HealthCheckReport,
    HealthPlan,
    HealthPlanTask,
    HealthReportAnalysis,
    HealthService,
    RiskAssessment,
)

# Service name -> (category, priority) used by rule matching.  Only real
# catalog rows (loaded from DB) are ever returned; names here are lookup keys.
_REPORT_ABNORMAL_SERVICES = ("复查预约", "体检结果咨询")
_PLAN_SERVICE_KEYS: dict[str, tuple[str, ...]] = {
    "nutrition": ("营养评估", "个性化饮食指导"),
    "exercise": ("运动能力评估", "健身指导"),
    "sleep": ("睡眠健康讲座", "营养评估"),
}
_RISK_SERVICES = ("慢病健康管理咨询",)


async def list_active_services(session: AsyncSession) -> list[HealthService]:
    return list(
        (
            await session.scalars(
                select(HealthService)
                .where(HealthService.status == "active")
                .order_by(HealthService.sort_order, HealthService.name)
            )
        ).all()
    )


async def _latest_report_with_analysis(session: AsyncSession, user_id: UUID) -> tuple[HealthCheckReport | None, HealthReportAnalysis | None]:
    report = await session.scalar(
        select(HealthCheckReport)
        .where(HealthCheckReport.user_id == user_id, HealthCheckReport.parse_status == "parsed")
        .order_by(HealthCheckReport.report_date.desc())
        .limit(1)
    )
    analysis = None
    if report is not None:
        analysis = await session.scalar(
            select(HealthReportAnalysis)
            .where(
                HealthReportAnalysis.report_id == report.id,
                HealthReportAnalysis.user_id == user_id,
                HealthReportAnalysis.analysis_status == "completed",
            )
            .order_by(HealthReportAnalysis.created_at.desc())
            .limit(1)
        )
    return report, analysis


async def _abnormal_indicators(session: AsyncSession, report_id: UUID) -> list[dict]:
    rows = list(
        (
            await session.scalars(
                select(HealthCheckIndicator)
                .where(HealthCheckIndicator.report_id == report_id, HealthCheckIndicator.flag.in_(["high", "low"]))
                .order_by(HealthCheckIndicator.category, HealthCheckIndicator.item_name)
                .limit(5)
            )
        ).all()
    )
    return [
        {
            "name": item.item_name,
            "value": item.value_text or str(item.value) if item.value is not None else None,
            "flag": item.flag,
            "reference": item.reference_text,
            "unit": item.unit,
        }
        for item in rows
    ]


async def _active_plan(session: AsyncSession, user_id: UUID) -> HealthPlan | None:
    return await session.scalar(
        select(HealthPlan)
        .where(HealthPlan.user_id == user_id, HealthPlan.status == "active")
        .order_by(HealthPlan.created_at.desc())
        .limit(1)
    )


async def _plan_task_types(session: AsyncSession, plan_id: UUID) -> set[str]:
    rows = set(
        (
            await session.scalars(
                select(HealthPlanTask.task_type).where(HealthPlanTask.plan_id == plan_id, HealthPlanTask.day_index <= 7)
            )
        ).all()
    )
    return {value for value in rows if value}


async def _risk_levels(session: AsyncSession, user_id: UUID) -> list[str]:
    rows = await session.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.user_id == user_id, RiskAssessment.level.in_(["high", "attention", "medium"]))
        .order_by(RiskAssessment.assessed_at.desc())
    )
    return list(rows.all())


async def build_recommendation_candidates(session: AsyncSession, user_id: UUID) -> list[dict]:
    """Return up to 3 rule-matched candidate recommendations.

    Each candidate: service_id / service_name / category / reason_code /
    evidence (structured) / source (labels) / priority.
    """
    services = await list_active_services(session)
    by_name = {service.name: service for service in services}
    picked: list[dict] = []
    seen: set[UUID] = set()

    def add(key: str, reason_code: str, evidence: list[dict], sources: list[str], priority: int) -> None:
        service = by_name.get(key)
        if service is None or service.id in seen:
            return
        seen.add(service.id)
        picked.append({
            "service_id": str(service.id),
            "service_name": service.name,
            "category": service.category,
            "reason_code": reason_code,
            "evidence": evidence,
            "source": sources,
            "priority": priority,
        })

    report, analysis = await _latest_report_with_analysis(session, user_id)
    abnormal = await _abnormal_indicators(session, report.id) if report is not None else []
    if abnormal:
        sources = ["Health Report"]
        if analysis is not None:
            sources.append("AI Report Analysis")
        add(_REPORT_ABNORMAL_SERVICES[0], "REPORT_ABNORMAL", abnormal, sources, 90)
        add(_REPORT_ABNORMAL_SERVICES[1], "REPORT_ABNORMAL", abnormal, sources, 85)

    plan = await _active_plan(session, user_id)
    if plan is not None:
        task_types = await _plan_task_types(session, plan.id)
        plan_evidence = [{"plan_name": plan.plan_name, "plan_type": plan.plan_type, "goal": plan.goal}]
        matched_plan_type = plan.plan_type
        if plan.plan_type == "general" and "nutrition" in task_types:
            matched_plan_type = "nutrition"
        elif plan.plan_type == "general" and "exercise" in task_types:
            matched_plan_type = "exercise"
        for key in _PLAN_SERVICE_KEYS.get(matched_plan_type, ()):
            add(key, f"PLAN_{matched_plan_type.upper()}", plan_evidence, ["Health Plan"], 80)

    risks = await _risk_levels(session, user_id)
    if risks and picked and len(picked) < 3:
        risk_evidence = [{"risk_type": row.risk_type, "level": row.level} for row in risks[:2]]
        add(_RISK_SERVICES[0], "RISK_ATTENTION", risk_evidence, ["Health Risk"], 70)

    return picked[:3]
