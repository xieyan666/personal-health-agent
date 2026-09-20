"""Administrator Agent registry and runtime monitoring endpoints."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.auth.jwt import require_role
from backend.app.core.database import get_db
from backend.app.models import Agent, AgentRun, KnowledgeBase, Tool, ModelConfig, Conversation

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])
admin = require_role("admin", "company_admin", "system_admin")

class StatusPayload(BaseModel):
    status: str

class TestPayload(BaseModel):
    content: str
    conversation_id: UUID | None = None
    use_knowledge: bool = True
    use_profile: bool = True

def _status(value: str) -> str:
    return "enabled" if value in {"active", "enabled"} else "disabled"

async def _agent_view(session: AsyncSession, agent: Agent) -> dict[str, Any]:
    cfg = agent.config if isinstance(agent.config, dict) else {}
    tool_cfg = cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {}
    tool_ids = tool_cfg.get("tool_ids", []) if isinstance(tool_cfg.get("tool_ids", []), list) else []
    kb_ids = cfg.get("knowledge_base_ids", []) if isinstance(cfg.get("knowledge_base_ids", []), list) else []
    tools = (await session.execute(select(Tool).where(Tool.id.in_([UUID(str(x)) for x in tool_ids])))).scalars().all() if tool_ids else []
    kbs = (await session.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_([UUID(str(x)) for x in kb_ids])))).scalars().all() if kb_ids else []
    model = await session.get(ModelConfig, agent.model_config_id) if agent.model_config_id else None
    now = datetime.now(timezone.utc); start = now.replace(hour=0, minute=0, second=0, microsecond=0); week = now - timedelta(days=7)
    today = (await session.execute(select(func.count(AgentRun.id)).where(AgentRun.agent_id == agent.id, AgentRun.started_at >= start))).scalar_one()
    week_count = (await session.execute(select(func.count(AgentRun.id)).where(AgentRun.agent_id == agent.id, AgentRun.started_at >= week))).scalar_one()
    failed = (await session.execute(select(func.count(AgentRun.id)).where(AgentRun.agent_id == agent.id, AgentRun.started_at >= week, AgentRun.status.in_(["failed", "error"])))) .scalar_one()
    runs = (await session.execute(select(AgentRun).where(AgentRun.agent_id == agent.id).order_by(AgentRun.started_at.desc()).limit(20))).scalars().all()
    success = sum(1 for r in runs if r.status == "succeeded")
    latencies = [r.latency_ms for r in runs if r.latency_ms is not None]
    return {"id": str(agent.id), "name": agent.name, "slug": agent.code, "type": "Supervisor" if (agent.category or "").lower() == "supervisor" or "supervisor" in (agent.code or "") else "Specialist", "status": _status(agent.status), "enabled": _status(agent.status) == "enabled", "domain": agent.category or "未配置", "description": agent.description or "", "model": model.name if model else "未配置", "model_name": model.model_name if model else None, "knowledgeBases": [{"id": str(k.id), "name": k.name, "status": k.status} for k in kbs], "tools": [{"id": str(t.id), "name": t.display_name or t.name, "status": t.status} for t in tools], "todayRuns": today, "weekRuns": week_count, "exceptions": failed, "successRate": round(success / len(runs) * 100, 1) if runs else None, "latency": round(sum(latencies) / len(latencies) / 1000, 2) if latencies else None, "toolCalls": None, "hitRate": None, "createdAt": agent.created_at.isoformat() if agent.created_at else None, "updatedAt": agent.updated_at.isoformat() if agent.updated_at else None, "responsibilities": (cfg.get("responsibilities") if isinstance(cfg.get("responsibilities"), list) else []), "capabilities": {"route": agent.category == "supervisor" or "supervisor" in (agent.code or ""), "tool": bool(tool_ids), "knowledge": bool(kb_ids), "output": bool(cfg.get("output_control"))}, "config": cfg}

@router.get("")
async def list_agents(_: Any = Depends(admin), session: AsyncSession = Depends(get_db)):
    agents = (await session.execute(select(Agent).order_by(Agent.created_at))).scalars().all()
    return {"items": [await _agent_view(session, a) for a in agents]}

@router.get("/summary")
async def summary(_: Any = Depends(admin), session: AsyncSession = Depends(get_db)):
    rows = (await session.execute(select(Agent))).scalars().all(); now = datetime.now(timezone.utc); start = now.replace(hour=0, minute=0, second=0, microsecond=0); week = now - timedelta(days=7)
    today = (await session.execute(select(func.count(AgentRun.id)).where(AgentRun.started_at >= start))).scalar_one(); failures = (await session.execute(select(func.count(AgentRun.id)).where(AgentRun.started_at >= week, AgentRun.status.in_(["failed", "error"])))) .scalar_one()
    return {"total": len(rows), "enabled": sum(_status(a.status) == "enabled" for a in rows), "todayRuns": today, "recentExceptions": failures}

@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, _: Any = Depends(admin), session: AsyncSession = Depends(get_db)):
    agent = await session.get(Agent, agent_id)
    if not agent: raise HTTPException(404, "Agent not found")
    return await _agent_view(session, agent)

@router.get("/{agent_id}/runs")
async def agent_runs(agent_id: UUID, days: int = Query(7, ge=1, le=90), _: Any = Depends(admin), session: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days); runs = (await session.execute(select(AgentRun).where(AgentRun.agent_id == agent_id, AgentRun.started_at >= since).order_by(AgentRun.started_at.desc()))).scalars().all()
    return {"items": [{"id": str(r.id), "time": r.started_at.isoformat() if r.started_at else None, "input": r.input_summary or "", "status": r.status, "latency": r.latency_ms, "error": r.error_message} for r in runs], "trend": []}

@router.patch("/{agent_id}/status")
async def update_status(agent_id: UUID, payload: StatusPayload, _: Any = Depends(admin), session: AsyncSession = Depends(get_db)):
    if payload.status not in {"active", "disabled", "enabled", "inactive"}: raise HTTPException(422, "Invalid status")
    agent = await session.get(Agent, agent_id)
    if not agent: raise HTTPException(404, "Agent not found")
    agent.status = "active" if payload.status in {"active", "enabled"} else "disabled"; await session.commit(); await session.refresh(agent); return await _agent_view(session, agent)

@router.post("/{agent_id}/test")
async def test_agent(agent_id: UUID, payload: TestPayload, current: Any = Depends(admin), session: AsyncSession = Depends(get_db)):
    if not payload.content.strip(): raise HTTPException(422, "content must not be empty")
    conversation_id = payload.conversation_id
    if conversation_id is None:
        agent = await session.get(Agent, agent_id)
        if not agent: raise HTTPException(404, "Agent not found")
        conversation = Conversation(user_id=current.id, agent_id=agent_id, title="Agent 管理测试", status="active", context={})
        session.add(conversation); await session.flush(); conversation_id = conversation.id
    from backend.app.agent.runtime import AgentRuntimeService
    result = await AgentRuntimeService(session).run(current.id, agent_id, conversation_id, payload.content)
    return {"status": result.run_status, "run_id": str(result.run_id), "assistant_content": result.assistant_content, "steps": [{"name": "Agent Runtime", "status": "completed"}]}
