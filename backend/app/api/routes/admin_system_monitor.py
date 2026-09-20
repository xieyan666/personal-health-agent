"""System monitoring control center (JWT + RBAC).

Aggregates real health checks (PostgreSQL / Redis / Qdrant / MinIO /
FastAPI / Agent Runtime / Model Gateway / Embedding), lightweight request
metrics, agent_runs, background task states and persistent system alerts.
No mocked runtime data.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db, check_database_connection
from backend.app.core.minio import check_minio_connection
from backend.app.core.qdrant import check_qdrant_connection
from backend.app.core.redis import check_redis_connection
from backend.app.models import Agent, AgentRun, AuditLog, Document, KnowledgeBase, ModelConfig, RequestMetric, SystemAlert

router = APIRouter(prefix="/system-monitor", tags=["admin-system-monitor"])
admin = require_role("admin", "company_admin", "system_admin")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

async def _timed(coro, default: Any = None):
    started = time.monotonic()
    try:
        result = await coro
        return result, round((time.monotonic() - started) * 1000)
    except Exception:
        return default, round((time.monotonic() - started) * 1000)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Service health checks
# --------------------------------------------------------------------------

async def _check_postgres() -> dict:
    ok, latency = await _timed(check_database_connection())
    return {"key": "postgres", "name": "PostgreSQL", "status": "ok" if ok else "error", "latency_ms": latency, "detail": "SELECT 1" if ok else "连接失败"}


async def _check_redis() -> dict:
    ok, latency = await _timed(check_redis_connection())
    return {"key": "redis", "name": "Redis", "status": "ok" if ok else "error", "latency_ms": latency, "detail": "PING" if ok else "连接失败"}


async def _check_qdrant() -> dict:
    ok, latency = await _timed(check_qdrant_connection())
    return {"key": "qdrant", "name": "Qdrant", "status": "ok" if ok else "error", "latency_ms": latency, "detail": "Collections" if ok else "连接失败"}


def _check_minio() -> dict:
    started = time.monotonic()
    try:
        ok = check_minio_connection()
        return {"key": "minio", "name": "MinIO", "status": "ok" if ok else "error", "latency_ms": round((time.monotonic() - started) * 1000), "detail": "桶检查" if ok else "连接失败"}
    except Exception:
        return {"key": "minio", "name": "MinIO", "status": "error", "latency_ms": round((time.monotonic() - started) * 1000), "detail": "连接失败"}


def _check_fastapi() -> dict:
    return {"key": "fastapi", "name": "FastAPI", "status": "ok", "latency_ms": 0, "detail": "本服务健康检查通过"}


async def _check_agent_runtime(session: AsyncSession) -> dict:
    started = time.monotonic()
    agents = list((await session.scalars(select(Agent).where(Agent.status == "active"))).all())
    if not agents:
        return {"key": "agent_runtime", "name": "Agent Runtime", "status": "error", "latency_ms": round((time.monotonic() - started) * 1000), "detail": "无启用中的 Agent"}
    return {"key": "agent_runtime", "name": "Agent Runtime", "status": "ok", "latency_ms": round((time.monotonic() - started) * 1000), "detail": f"{len(agents)} 个启用 Agent"}


async def _check_model_gateway(session: AsyncSession) -> dict:
    started = time.monotonic()
    config = await session.scalar(
        select(ModelConfig).where(ModelConfig.model_type == "chat", ModelConfig.is_default, ModelConfig.status == "active")
    )
    if config is None:
        return {"key": "model_gateway", "name": "Model Gateway", "status": "error", "latency_ms": round((time.monotonic() - started) * 1000), "detail": "未找到启用中的默认 Chat 模型"}
    return {"key": "model_gateway", "name": "Model Gateway", "status": "ok", "latency_ms": round((time.monotonic() - started) * 1000), "detail": f"默认 {config.name}"}


async def _check_embedding(session: AsyncSession) -> dict:
    started = time.monotonic()
    config = await session.scalar(
        select(ModelConfig).where(ModelConfig.model_type == "embedding", ModelConfig.is_default, ModelConfig.status == "active")
    )
    if config is None:
        return {"key": "embedding", "name": "Embedding Model", "status": "unconfigured", "latency_ms": round((time.monotonic() - started) * 1000), "detail": "未配置默认 Embedding 模型"}
    fake = "fake" in (config.model_name or "").lower() or (config.parameters or {}).get("purpose") == "test"
    return {
        "key": "embedding",
        "name": "Embedding Model",
        "status": "unconfigured" if fake else "ok",
        "latency_ms": round((time.monotonic() - started) * 1000),
        "detail": ("当前为 TEST 模型（未配置正式 Embedding）" if fake else f"默认 {config.name} · {config.vector_dimension or '?'} 维"),
    }


async def _check_rag(session: AsyncSession) -> dict:
    started = time.monotonic()
    kbs = list((await session.scalars(select(KnowledgeBase).where(KnowledgeBase.status == "active"))).all())
    indexed = int((await session.scalar(select(func.count(Document.id)).where(Document.status == "indexed"))) or 0)
    return {
        "key": "rag", "name": "Knowledge RAG", "status": "ok" if kbs else "unconfigured",
        "latency_ms": round((time.monotonic() - started) * 1000),
        "detail": f"{len(kbs)} 个知识库 · {indexed} 份已索引文档" if kbs else "暂无知识库",
    }


# --------------------------------------------------------------------------
# System resources (best effort, never fabricated)
# --------------------------------------------------------------------------

def _system_resources() -> dict:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uptime = time.time() - psutil.boot_time()
        return {
            "available": True,
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used_gb": round(memory.used / 1024 ** 3, 1),
            "memory_total_gb": round(memory.total / 1024 ** 3, 1),
            "disk_percent": round(disk.percent, 1),
            "uptime_hours": round(uptime / 3600, 1),
        }
    except Exception:
        return {"available": False, "note": "当前环境无法可靠读取系统资源，暂无监控数据"}


# --------------------------------------------------------------------------
# API metrics (from request_metrics)
# --------------------------------------------------------------------------

async def _api_metrics(session: AsyncSession) -> dict:
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    async def count_since(boundary: datetime) -> int:
        return int((await session.scalar(select(func.count(RequestMetric.id)).where(RequestMetric.created_at >= boundary))) or 0)

    async def avg_duration_since(boundary: datetime) -> float | None:
        value = await session.scalar(select(func.avg(RequestMetric.duration_ms)).where(RequestMetric.created_at >= boundary))
        return round(float(value), 1) if value is not None else None

    async def error_rate_since(boundary: datetime) -> float | None:
        total = await count_since(boundary)
        if total == 0:
            return None
        errors = int((await session.scalar(select(func.count(RequestMetric.id)).where(RequestMetric.created_at >= boundary, RequestMetric.status_code >= 500))) or 0)
        return round(errors / total * 100, 1)

    today_total = await count_since(today)
    today_errors = int((await session.scalar(select(func.count(RequestMetric.id)).where(RequestMetric.created_at >= today, RequestMetric.status_code >= 500))) or 0)
    today_success_rate = round((today_total - today_errors) / today_total * 100, 1) if today_total else None

    slow_rows = (
        await session.execute(
            select(
                RequestMetric.path, RequestMetric.method,
                func.avg(RequestMetric.duration_ms).label("avg_ms"),
                func.count(RequestMetric.id).label("calls"),
                func.avg(case((RequestMetric.status_code >= 500, 1.0), else_=0.0)).label("err_rate"),
            )
            .where(RequestMetric.created_at >= week_ago)
            .group_by(RequestMetric.path, RequestMetric.method)
            .order_by(func.avg(RequestMetric.duration_ms).desc())
            .limit(8)
        )
    ).all()
    slow = [
        {"path": row[0], "method": row[1], "avg_ms": round(float(row[2]), 1), "calls": int(row[3]), "error_rate": round(float(row[4]) * 100, 1)}
        for row in slow_rows
    ]

    # Trend buckets are computed with a single grouped query per range.
    async def trend(boundary: datetime, step: timedelta, count: int) -> list[dict]:
        rows = (
            await session.execute(
                select(func.date_trunc("hour" if step < timedelta(days=1) else "day", RequestMetric.created_at).label("bucket"), func.count(RequestMetric.id))
                .where(RequestMetric.created_at >= boundary)
                .group_by("bucket")
                .order_by("bucket")
            )
        ).all()
        mapping = {row[0].strftime("%H:%M") if step < timedelta(days=1) else row[0].strftime("%m-%d"): int(row[1]) for row in rows}
        result: list[dict] = []
        cursor = boundary
        while cursor <= now:
            label = cursor.strftime("%H:%M") if step < timedelta(days=1) else cursor.strftime("%m-%d")
            result.append({"label": label, "count": mapping.get(label, 0)})
            cursor += step
        return result[:count]

    return {
        "today": {"total": today_total, "errors": today_errors, "success_rate": today_success_rate, "avg_duration_ms": await avg_duration_since(today)},
        "trend": {
            "hour": await trend(hour_ago, timedelta(minutes=10), 6),
            "day": await trend(day_ago, timedelta(hours=2), 12),
            "week": await trend(week_ago, timedelta(days=1), 7),
        },
        "slow_endpoints": slow,
    }


# --------------------------------------------------------------------------
# Agent metrics (from agent_runs)
# --------------------------------------------------------------------------

async def _agent_metrics(session: AsyncSession) -> dict:
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_runs = int((await session.scalar(select(func.count(AgentRun.id)).where(AgentRun.created_at >= today))) or 0)
    succeeded = int((await session.scalar(select(func.count(AgentRun.id)).where(AgentRun.created_at >= today, AgentRun.status == "succeeded"))) or 0)
    today_success_rate = round(succeeded / today_runs * 100, 1) if today_runs else None
    avg_latency = await session.scalar(select(func.avg(AgentRun.latency_ms)).where(AgentRun.latency_ms.is_not(None)))
    exceptions = int((await session.scalar(select(func.count(AgentRun.id)).where(AgentRun.status != "succeeded"))) or 0)
    recent_errors = list(
        (
            await session.scalars(
                select(AgentRun).where(AgentRun.status != "succeeded").order_by(AgentRun.created_at.desc()).limit(5)
            )
        ).all()
    )
    agents = {agent.id: agent.name for agent in (await session.scalars(select(Agent))).all()}
    return {
        "today_runs": today_runs,
        "today_success_rate": today_success_rate,
        "avg_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
        "exceptions": exceptions,
        "recent_errors": [
            {
                "id": str(run.id), "agent": agents.get(run.agent_id, "未知"), "error_code": run.error_code,
                "error_message": (run.error_message or "")[:200], "trace_id": str(run.trace_id),
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in recent_errors
        ],
    }


# --------------------------------------------------------------------------
# Background tasks (reuse document status + agent_runs)
# --------------------------------------------------------------------------

async def _task_metrics(session: AsyncSession) -> dict:
    docs = list((await session.scalars(select(Document).order_by(Document.updated_at.desc()).limit(30))).all())
    runs = list(
        (
            await session.scalars(
                select(AgentRun).where(AgentRun.status.in_(["pending", "running"])).order_by(AgentRun.created_at.desc()).limit(10)
            )
        ).all()
    )
    tasks = []
    for doc in docs:
        status = doc.status
        state = "running" if status == "processing" else "success" if status == "indexed" else "failed" if status == "failed" else "pending"
        tasks.append({
            "id": str(doc.id), "name": doc.name[:60], "task_type": "Document 解析/索引", "source": "documents",
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "status": state, "error": doc.error_message, "related": doc.status,
        })
    for run in runs:
        tasks.append({
            "id": str(run.id), "name": f"Agent Run {str(run.id)[:8]}", "task_type": "Agent Run", "source": "agent_runs",
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": None, "status": run.status, "error": run.error_message, "related": run.status,
        })
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = int((await session.scalar(select(func.count(Document.id)).where(Document.status == "indexed", Document.updated_at >= today))) or 0)
    failed = int((await session.scalar(select(func.count(Document.id)).where(Document.status == "failed"))) or 0)
    running = sum(1 for task in tasks if task["status"] == "running")
    waiting = sum(1 for task in tasks if task["status"] == "pending")
    return {"running": running, "waiting": waiting, "completed_today": completed_today, "failed": failed, "tasks": tasks}


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@router.get("/overview")
async def monitor_overview(session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    services = [
        await _check_postgres(), await _check_redis(), await _check_qdrant(), await asyncio.to_thread(_check_minio),
        _check_fastapi(), await _check_agent_runtime(session), await _check_model_gateway(session), await _check_embedding(session), await _check_rag(session),
    ]
    ok_count = sum(1 for item in services if item["status"] == "ok")
    degraded = sum(1 for item in services if item["status"] in ("error", "unconfigured"))
    if ok_count == len(services):
        overall = "normal"
    elif degraded and ok_count:
        overall = "partial"
    else:
        overall = "critical"

    api_metrics = await _api_metrics(session)
    agent_metrics = await _agent_metrics(session)
    task_metrics = await _task_metrics(session)
    alerts = await _alert_stats(session)

    return {
        "overall_status": overall,
        "services": services,
        "services_available": f"{ok_count} / {len(services)}",
        "resources": _system_resources(),
        "api": api_metrics,
        "agents": agent_metrics,
        "tasks": task_metrics,
        "alerts": alerts,
        "checked_at": _now().isoformat(),
    }


@router.get("/tasks")
async def monitor_tasks(session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    return await _task_metrics(session)


@router.get("/alerts")
async def monitor_alerts(limit: int = 50, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    rows = list((await session.scalars(select(SystemAlert).order_by(SystemAlert.created_at.desc()).limit(min(limit, 200)))).all())
    return [
        {
            "id": str(alert.id), "source": alert.source, "level": alert.level, "error_code": alert.error_code,
            "message": alert.message[:300], "trace_id": str(alert.trace_id) if alert.trace_id else None,
            "details": alert.details, "status": alert.status,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        }
        for alert in rows
    ]


async def _alert_stats(session: AsyncSession) -> dict:
    open_count = int((await session.scalar(select(func.count(SystemAlert.id)).where(SystemAlert.status.in_(["open", "processing"])))) or 0)
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_total = int((await session.scalar(select(func.count(SystemAlert.id)).where(SystemAlert.created_at >= today))) or 0)
    return {"open": open_count, "today_total": today_total}


class AlertStatusRequest(BaseModel):
    status: str


@router.post("/alerts/{alert_id}/status")
async def update_alert_status(alert_id: UUID, payload: AlertStatusRequest, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    if payload.status not in ("open", "processing", "resolved", "ignored"):
        raise HTTPException(422, "状态仅支持 open / processing / resolved / ignored")
    alert = await session.get(SystemAlert, alert_id)
    if alert is None:
        raise HTTPException(404, "告警不存在")
    alert.status = payload.status
    alert.resolved_at = _now() if payload.status in ("resolved", "ignored") else None
    await session.commit()
    return {"id": str(alert.id), "status": alert.status}


@router.get("/logs")
async def monitor_logs(source: str | None = None, level: str | None = None, trace_id: str | None = None, limit: int = 50, session: AsyncSession = Depends(get_db), _: Any = Depends(admin)):
    """Lightweight log view from audit_logs (sensitive fields are never exposed)."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 200))
    rows = list((await session.scalars(stmt)).all())
    result = []
    for row in rows:
        details = dict(row.details or {})
        # Never surface sensitive payloads; keep only structural keys.
        safe_details = {key: value for key, value in details.items() if key in {"scope", "purpose", "action", "actor_type", "actor_id", "grantee_type"}}
        item = {
            "id": str(row.id), "time": row.created_at.isoformat() if row.created_at else None,
            "service": "audit", "level": "INFO" if row.outcome == "success" else "WARNING",
            "message": f"{row.action} · {row.resource_type} · {row.outcome}",
            "trace_id": str(row.trace_id) if row.trace_id else None,
            "action": row.action, "resource_type": row.resource_type, "outcome": row.outcome, "details": safe_details,
        }
        if source and source != "audit":
            continue
        if level and item["level"] != level:
            continue
        if trace_id and item["trace_id"] != trace_id:
            continue
        result.append(item)
    return result
