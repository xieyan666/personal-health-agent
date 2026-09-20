"""Health Supervisor stage for service recommendations.

Pipeline: rule candidates (ServiceRecommendationTool, no LLM)
-> fingerprint cache -> DeepSeek natural-language reasons -> Pydantic
validation -> Safety Guard (soften diagnostic language) -> response.

Rule matching decides *what* to recommend; the AI only rewrites the structured
evidence into a short, factual Chinese sentence.  On any AI failure the
recommendation still works with a rule-derived fallback reason.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import ServiceError
from backend.app.model_gateway.chat import ChatInput, chat_provider_for, normalize_chat_parameters
from backend.app.schemas.health_services import ServiceReasonList
from backend.app.tools.service_recommendation import build_recommendation_candidates, list_active_services

CACHE_TTL_SECONDS = 600  # 10 minutes
_cache: dict[str, tuple[float, dict]] = {}

_RECOMMENDATION_SYSTEM_PROMPT = """你是企业员工生命健康平台中的健康服务推荐解释助手。

你的任务：基于候选服务的结构化证据，为每条候选服务生成一句简洁、基于事实的中文推荐理由。

严格遵守：

1. 只能使用输入证据，禁止编造不存在的检查项目、数值或结论。
2. 只陈述事实：数值高于/低于报告参考范围、健康计划包含某目标、存在风险提示等。
3. 不进行疾病诊断；禁止使用"确诊""患有""是某某病"等确定性表达。
4. 不给出复查时间建议（如"1-3个月""半年后"），除非输入证据中已明确提供时间。
5. 推荐只是健康服务匹配，不替代医疗诊断。
6. 每条理由 20-45 字，语句通顺、可直接展示给员工。
7. 输出必须是严格 JSON，不要 Markdown 包裹，不要额外文字。

输出 JSON 结构：
{"reasons": [{"service_id": "候选中的服务ID", "reason": "推荐理由"}]}
reasons 数组必须与输入候选一一对应。"""


def _soften(text: str) -> str:
    import re
    for pattern, replacement in (
        (re.compile(r"确诊|诊断为|患有.{0,8}病|患上了|得了|癌症|恶性肿瘤", re.IGNORECASE), "可能存在风险"),
        (re.compile(r"肯定|一定|必然|百分百", re.IGNORECASE), "建议"),
        (re.compile(r"非常危险|极其严重|后果严重", re.IGNORECASE), "需要关注"),
    ):
        text = pattern.sub(replacement, text)
    return text


async def _data_fingerprint(session: AsyncSession, user_id: UUID) -> str:
    """Fingerprint of the health data that drives recommendations."""
    from backend.app.models import (
        HealthCheckIndicator,
        HealthCheckReport,
        HealthPlan,
        HealthReportAnalysis,
        HealthService,
        RiskAssessment,
    )
    parts: list[str] = [str(user_id)]
    services_version = await session.scalar(select(func.max(HealthService.updated_at)))
    if services_version is not None:
        parts.append(f"svc:{services_version.isoformat()}")
    report = await session.scalar(
        select(HealthCheckReport)
        .where(HealthCheckReport.user_id == user_id, HealthCheckReport.parse_status == "parsed")
        .order_by(HealthCheckReport.report_date.desc()).limit(1)
    )
    if report is not None:
        abnormal = (await session.scalars(
            select(HealthCheckIndicator.code)
            .where(HealthCheckIndicator.report_id == report.id, HealthCheckIndicator.flag.in_(["high", "low"]))
        )).all()
        parts.append(f"report:{report.id}:{sorted(str(value) for value in abnormal)}")
    analysis = await session.scalar(
        select(HealthReportAnalysis)
        .where(HealthReportAnalysis.report_id == report.id, HealthReportAnalysis.user_id == user_id, HealthReportAnalysis.analysis_status == "completed")
        .order_by(HealthReportAnalysis.created_at.desc()).limit(1)
    ) if report is not None else None
    if analysis is not None:
        parts.append(f"analysis:{analysis.id}")
    plan = await session.scalar(
        select(HealthPlan)
        .where(HealthPlan.user_id == user_id, HealthPlan.status == "active")
        .order_by(HealthPlan.created_at.desc()).limit(1)
    )
    if plan is not None:
        parts.append(f"plan:{plan.id}:{plan.plan_type}")
    risks = sorted(
        str(value)
        for value in (await session.scalars(
            select(RiskAssessment.id).where(RiskAssessment.user_id == user_id, RiskAssessment.level.in_(["high", "attention", "medium"]))
        )).all()
    )
    parts.append(f"risk:{risks}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _rule_fallback_reason(candidate: dict) -> str:
    evidence = candidate.get("evidence") or []
    code = candidate.get("reason_code", "")
    if code == "REPORT_ABNORMAL":
        names = "、".join(str(item.get("name")) for item in evidence[:3])
        return f"体检中发现 {names} 高于/低于报告参考范围，建议关注后续变化并考虑相关复查服务。"
    if code.startswith("PLAN_"):
        plan_name = (evidence[0].get("plan_name") if evidence else None) or "当前健康计划"
        return f"结合 {plan_name} 的目标，建议匹配相应的健康服务。"
    if code == "RISK_ATTENTION":
        return "当前存在需要关注的风险因素，建议获得专业的健康管理咨询。"
    return "根据你的健康状态，推荐该项健康服务。"


async def get_service_recommendations(session: AsyncSession, user_id: UUID, *, environment: dict[str, str] | None = None) -> dict:
    """Return recommendations with AI-generated reasons (cached by data fingerprint)."""
    candidates = await build_recommendation_candidates(session, user_id)
    if not candidates:
        return {"recommendations": [], "ai_status": "empty"}

    fingerprint = await _data_fingerprint(session, user_id)
    cache_key = f"svc-rec:{fingerprint}"
    cached = _cache.get(cache_key)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]

    reasons_by_id: dict[str, str] = {}
    ai_status = "ok"
    try:
        reasons_by_id = await _ai_reasons(candidates, environment)
    except Exception:
        ai_status = "fallback"

    recommendations = []
    for candidate in candidates:
        service_id = candidate["service_id"]
        reason = reasons_by_id.get(service_id)
        if not reason:
            reason = _rule_fallback_reason(candidate)
            ai_status = "fallback" if ai_status != "error" else ai_status
        reason = _soften(reason)
        recommendations.append({
            "service_id": service_id,
            "service_name": candidate["service_name"],
            "category": candidate["category"],
            "priority": candidate["priority"],
            "reason": reason,
            "sources": candidate["source"],
            "ai_generated": service_id in reasons_by_id,
        })

    payload = {"recommendations": recommendations, "ai_status": ai_status}
    _cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, payload)
    return payload


async def _ai_reasons(candidates: list[dict], environment: dict[str, str] | None) -> dict[str, str]:
    provider = chat_provider_for(
        "deepseek",
        secret_ref="env:DEEPSEEK_API_KEY",
        endpoint=None,
        environment=environment,
    )
    payload = [{
        "service_id": candidate["service_id"],
        "service_name": candidate["service_name"],
        "reason_code": candidate["reason_code"],
        "evidence": candidate["evidence"],
        "sources": candidate["source"],
    } for candidate in candidates]
    import asyncio
    result = await asyncio.to_thread(
        provider.chat,
        [ChatInput("system", _RECOMMENDATION_SYSTEM_PROMPT), ChatInput("user", json.dumps({"candidates": payload}, ensure_ascii=False))],
        model_name="deepseek-chat",
        parameters=normalize_chat_parameters({"temperature": 0.3, "max_tokens": 800}),
    )
    parsed = _parse_json(result.content)
    validated = ServiceReasonList.model_validate(parsed)
    reasons: dict[str, str] = {}
    for item in validated.reasons:
        reasons[str(item.service_id)] = item.reason.strip()
    return reasons


def _parse_json(raw: str) -> dict:
    import re
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("not an object")
    return value
