"""AI report interpretation orchestration: Supervisor route + persistence.

This service plays the Health Supervisor role for the explicit
``report_analysis`` task.  Because the user has already clicked "AI智能解读"
the task type is known, so no LLM intent classification is performed.

Cache rule: a completed analysis is returned directly unless the parsed
indicator set changed or the user explicitly re-analyzes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.health_supervisor.health_report_interpretation.agent import AGENT_NAME, ReportAgent
from backend.app.exceptions import ForbiddenError, NotFoundError, ServiceError
from backend.app.models import Agent, AgentRun, HealthCheckReport, KnowledgeBase
from backend.app.services.retrieval import RetrievalService
from backend.app.schemas.health_report_analysis import ReportAnalysisResponse
from backend.app.services.notification_service import create_notification
from backend.app.tools.health_profile import get_report_profile_context
from backend.app.tools.report import get_report_analysis_context

ANALYSIS_STATUS_PENDING = "pending"
ANALYSIS_STATUS_PROCESSING = "processing"
ANALYSIS_STATUS_COMPLETED = "completed"
ANALYSIS_STATUS_FAILED = "failed"

VALID_ANALYSIS_STATUSES = {ANALYSIS_STATUS_PENDING, ANALYSIS_STATUS_PROCESSING, ANALYSIS_STATUS_COMPLETED, ANALYSIS_STATUS_FAILED}
PROCESSING_STALE_AFTER = timedelta(minutes=5)


class ReportAnalysisError(ServiceError):
    """A safe, user-facing analysis failure."""


def _input_fingerprint(context: dict) -> str:
    """Stable fingerprint of the parsed indicator set.

    Any change in item identity, value, flag or reference range invalidates
    the cached analysis.
    """
    items = context.get("items", [])
    payload = [
        (item.get("code"), item.get("value_text"), item.get("flag"), item.get("reference_text"), item.get("source_type"), item.get("confidence"))
        for item in items
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


async def get_owned_report(session: AsyncSession, report_id: UUID, user_id: UUID) -> HealthCheckReport:
    """Load a report and enforce strict ownership.

    A missing report is 404; a report owned by another employee is 403 so the
    frontend can surface "无权访问" without confirming the report exists.
    """
    report = await session.get(HealthCheckReport, report_id)
    if report is None:
        raise NotFoundError("体检报告不存在")
    if report.user_id != user_id:
        raise ForbiddenError("无权访问其他员工的体检报告")
    return report


async def get_latest_analysis(session: AsyncSession, report_id: UUID, user_id: UUID) -> dict | None:
    """Return the latest analysis payload for the report owner, or None."""
    await get_owned_report(session, report_id, user_id)
    from backend.app.models.health_report_analysis import HealthReportAnalysis
    analysis = await session.scalar(
        select(HealthReportAnalysis)
        .where(HealthReportAnalysis.report_id == report_id, HealthReportAnalysis.user_id == user_id)
        .order_by(HealthReportAnalysis.created_at.desc())
        .limit(1)
    )
    if analysis is None:
        return None
    return _serialise_analysis(analysis)


def _serialise_analysis(analysis) -> dict:
    payload = {
        "analysis_id": str(analysis.id),
        "report_id": str(analysis.report_id),
        "status": analysis.analysis_status,
        "error_message": analysis.error_message,
        "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
    }
    result = analysis.analysis_result or {}
    if isinstance(result, dict):
        inner = result.get("analysis")
        payload["analysis"] = inner if isinstance(inner, dict) else None
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        profile = meta.get("profile") if isinstance(meta.get("profile"), dict) else {}
        payload["meta"] = {
            "model": meta.get("model"),
            "profile_available": bool(profile and any(value is not None for value in profile.values())),
        }
    else:
        payload["analysis"] = None
    return payload


async def trigger_analysis(
    session: AsyncSession,
    user_id: UUID,
    report_id: UUID,
    *,
    force: bool = False,
    environment: dict[str, str] | None = None,
) -> tuple[dict, bool]:
    """Trigger (or reuse) an AI interpretation for the report owner.

    Returns ``(payload, cached)`` where ``cached`` is True when an existing
    completed analysis matches the current indicator set and was returned
    without invoking the model.
    """
    from backend.app.models.health_report_analysis import HealthReportAnalysis

    report = await get_owned_report(session, report_id, user_id)
    if report.parse_status != "parsed":
        raise ReportAnalysisError("报告尚未解析完成，无法进行 AI 解读")
    context = await get_report_analysis_context(session, user_id, report_id)
    if context is None or not context.get("items"):
        raise ReportAnalysisError("暂无可分析的结构化体检指标")

    fingerprint = _input_fingerprint(context)

    # Cache hit: latest completed analysis whose fingerprint matches.
    if not force:
        latest = await session.scalar(
            select(HealthReportAnalysis)
            .where(
                HealthReportAnalysis.report_id == report_id,
                HealthReportAnalysis.user_id == user_id,
                HealthReportAnalysis.analysis_status == ANALYSIS_STATUS_COMPLETED,
            )
            .order_by(HealthReportAnalysis.created_at.desc())
            .limit(1)
        )
        if latest is not None:
            result = latest.analysis_result or {}
            if isinstance(result, dict) and result.get("meta", {}).get("input_fingerprint") == fingerprint:
                return _serialise_analysis(latest), True

    # Idempotency: an in-flight processing row is returned as-is so concurrent
    # clicks do not fire parallel model calls.
    stale_before = datetime.now(timezone.utc) - PROCESSING_STALE_AFTER
    processing = await session.scalar(
        select(HealthReportAnalysis)
        .where(
            HealthReportAnalysis.report_id == report_id,
            HealthReportAnalysis.user_id == user_id,
            HealthReportAnalysis.analysis_status == ANALYSIS_STATUS_PROCESSING,
        )
        .order_by(HealthReportAnalysis.created_at.desc())
        .limit(1)
    )
    if processing is not None and processing.updated_at is not None:
        updated = processing.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated >= stale_before:
            return _serialise_analysis(processing), False

    analysis = HealthReportAnalysis(
        report_id=report_id,
        user_id=user_id,
        agent_name=AGENT_NAME,
        analysis_status=ANALYSIS_STATUS_PENDING,
    )
    session.add(analysis)
    await session.flush()

    trace_agent = await _find_trace_agent(session)
    run_id: UUID | None = None
    if trace_agent is not None:
        run = AgentRun(
            user_id=user_id,
            agent_id=trace_agent.id,
            conversation_id=None,
            status="pending",
            input_summary=f"报告解读请求 report_id={report_id}",
            risk_level="low",
            safety_status="safe",
        )
        session.add(run)
        await session.flush()
        run_id = run.id
        run.status = "running"
        await session.flush()

    analysis.agent_run_id = run_id
    analysis.analysis_status = ANALYSIS_STATUS_PROCESSING
    analysis.started_at = datetime.now(timezone.utc)
    await session.commit()

    profile = await get_report_profile_context(session, user_id)
    # A knowledge base only participates when an administrator has explicitly
    # bound it to the active Report Agent.  Report parsing remains data-first;
    # retrieved policy/guidance only supplements the explanation prompt.
    knowledge_context = await _report_knowledge_context(session, trace_agent, context)
    agent = ReportAgent(environment=environment)
    try:
        validated: ReportAnalysisResponse = await agent.analyze(context, profile, knowledge_context)
    except ReportAnalysisError:
        raise
    except ServiceError as exc:
        analysis.analysis_status = ANALYSIS_STATUS_FAILED
        analysis.error_message = str(exc)
        analysis.completed_at = datetime.now(timezone.utc)
        if run_id is not None:
            run = await session.get(AgentRun, run_id)
            if run is not None:
                run.status = "failed"
        await session.commit()
        raise
    except Exception as exc:
        analysis.analysis_status = ANALYSIS_STATUS_FAILED
        analysis.error_message = "AI 解读服务异常，请稍后重试"
        analysis.completed_at = datetime.now(timezone.utc)
        if run_id is not None:
            run = await session.get(AgentRun, run_id)
            if run is not None:
                run.status = "failed"
        await session.commit()
        raise ReportAnalysisError("AI 解读服务异常，请稍后重试") from exc

    stored = {
        "analysis": validated.model_dump(),
        "meta": {
            "input_fingerprint": fingerprint,
            "model": agent.last_model_used,
            "prompt_tokens": agent.last_prompt_tokens,
            "completion_tokens": agent.last_completion_tokens,
            "safety_guard": "passed",
            "profile": profile,
        },
    }
    analysis.analysis_result = stored
    analysis.analysis_status = ANALYSIS_STATUS_COMPLETED
    analysis.model_name = agent.last_model_used
    analysis.completed_at = datetime.now(timezone.utc)
    if run_id is not None:
        run = await session.get(AgentRun, run_id)
        if run is not None:
            run.status = "succeeded"
            run.output_summary = json.dumps(validated.model_dump(), ensure_ascii=False)[:2000]
            run.finished_at = datetime.now(timezone.utc)
    await session.commit()
    # commit() expires ORM attributes; refresh before serialising to avoid a
    # lazy-load inside the synchronous serializer.
    await session.refresh(analysis)
    await create_notification(
        session,
        analysis.user_id,
        "health_report",
        "AI体检解读已完成",
        "你的最新体检报告已完成AI解读，可在体检报告页面查看详情。",
        "/employee/reports",
    )
    return _serialise_analysis(analysis), False


async def _find_trace_agent(session: AsyncSession) -> Agent | None:
    for code in ("report_agent", "health_report_interpretation", "health-supervisor-system", "health_supervisor"):
        agent = await session.scalar(
            select(Agent).where(Agent.code == code, Agent.status == "active").order_by(Agent.created_at.desc()).limit(1)
        )
        if agent is not None:
            return agent
    return None


async def _report_knowledge_context(session: AsyncSession, agent: Agent | None, report_context: dict) -> str:
    """Retrieve only knowledge bases explicitly bound to the report agent."""
    if agent is None:
        return ""
    raw_ids = (agent.config or {}).get("knowledge_base_ids", [])
    if not isinstance(raw_ids, list):
        return ""
    query = "体检指标 健康管理建议 " + " ".join(
        str(item.get("name") or item.get("code") or "") for item in report_context.get("items", [])[:8]
    )
    snippets: list[str] = []
    retriever = RetrievalService(session)
    for raw_id in raw_ids[:5]:
        try:
            kb = await session.get(KnowledgeBase, UUID(str(raw_id)))
            if kb is None or kb.status != "active" or kb.embedding_model_config_id is None:
                continue
            results = await retriever.retrieve(kb.id, query, kb.embedding_model_config_id, top_k=2)
            snippets.extend(f"[{kb.name}] {item.content[:800]}" for item in results)
        except Exception:
            # RAG is optional enrichment for the report interpretation; an
            # unavailable collection never blocks the real report analysis.
            continue
    return "\n\n".join(snippets[:4])


async def assert_analysis_accessible(session: AsyncSession, report_id: UUID, user_id: UUID) -> None:
    await get_owned_report(session, report_id, user_id)
