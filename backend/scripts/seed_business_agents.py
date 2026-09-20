"""Idempotently register the six first-party health agents.

This seed only writes agent definitions.  Runtime execution remains centralized
in :class:`AgentRuntimeService` (including child runs and tool authorization).
It deliberately does not remove historical ``rag-*``/test agents.
"""
from __future__ import annotations

import asyncio
from sqlalchemy import select

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Agent, ModelConfig, ModelProvider, Tool


AGENTS = (
    ("health_supervisor", "Health Supervisor", "Supervisor", "统一识别健康意图并路由到专业 Agent；无法匹配时提供通用健康建议。"),
    ("report_agent", "Report Agent", "Specialist", "读取已授权的结构化体检指标，生成非诊断性的报告解读。"),
    ("sleep_agent", "Sleep Agent", "Specialist", "基于已授权睡眠趋势提供睡眠健康管理建议。"),
    ("risk_agent", "Risk Agent", "Specialist", "解释 Health Risk Engine 已计算的风险结果，不自行改写风险评分。"),
    ("mental_health_agent", "Mental Health Agent", "Specialist", "基于已授权心理自评与趋势提供非诊断性支持，并遵循 Safety Guard。"),
    ("health_plan_agent", "Health Plan Agent", "Specialist", "将已确认的健康建议整理为可执行计划；写入前必须获得用户确认。"),
)

SYSTEM_PROMPTS = {
    "health_supervisor": "你是 Health Supervisor Agent。识别员工健康意图并路由到合适的专业 Agent；无法匹配时提供通用健康管理建议。不要向用户暴露内部路由。所有建议非诊断性，遇到高风险情况提醒寻求专业帮助。",
    "report_agent": "你是 Report Agent。仅根据已授权的结构化体检指标进行非诊断性解读，说明发现、需要关注项和健康建议，不自行编造指标或判断疾病。",
    "sleep_agent": "你是 Sleep Agent。仅根据已授权的睡眠趋势和健康档案提供睡眠管理建议，不编造数据、不进行医疗诊断。",
    "risk_agent": "你是 Risk Agent。解释 Health Risk Engine 已计算的结构化风险结果，不重新计算或修改风险评分；输出非诊断性的原因、影响与建议。",
    "mental_health_agent": "你是 Mental Health Agent。基于已授权的心理自评与趋势提供非诊断性支持；遵循 Safety Guard，发现危机信号时优先提供专业支持与求助建议。",
    "health_plan_agent": "你是 Health Plan Agent。把已确认的健康建议整理为可执行计划；任何写入或变更必须在用户明确确认并通过授权后进行。",
}


async def main() -> None:
    async with AsyncSessionFactory() as session:
        model = await session.scalar(
            select(ModelConfig)
            .join(ModelProvider, ModelProvider.id == ModelConfig.provider_id)
            .where(ModelConfig.status == "active", ModelConfig.model_type == "chat")
            .order_by((ModelProvider.provider_type == "deepseek").desc(), ModelConfig.is_default.desc(), ModelConfig.created_at.desc())
            .limit(1)
        )
        existing: dict[str, Agent] = {}
        for code, name, category, description in AGENTS:
            agent = await session.scalar(select(Agent).where(Agent.code == code))
            if agent is None:
                agent = Agent(scope="system", code=code, name=name, category=category.lower(), description=description, status="active", config={})
                session.add(agent)
                await session.flush()
            agent.name, agent.category, agent.description, agent.status = name, category.lower(), description, "active"
            agent.config = {**(agent.config or {}), "system_prompt": SYSTEM_PROMPTS[code]}
            if model is not None:
                agent.model_config_id = model.id
            existing[code] = agent

        # Keep the coordinator's routing graph explicit and bounded.  The
        # runtime creates child AgentRun rows and reuses the root conversation.
        supervisor = existing["health_supervisor"]
        supervisor.config = {
            **(supervisor.config or {}),
            "multi_agent": {
                "enabled": True,
                "sub_agent_ids": [str(existing[c].id) for c in ("report_agent", "sleep_agent", "risk_agent", "mental_health_agent", "health_plan_agent")],
                "max_handoffs": 3,
            },
            "routing": {"fallback": "deepseek-chat", "domains": ["report", "sleep", "risk", "mental_health", "health_plan"]},
        }

        # Attach any already-registered first-party tools without inventing
        # database rows.  ToolService/Runtime still validates status and auth.
        candidates = {
            "report_agent": ("report_tool", "health_profile_tool", "knowledge_search"),
            "sleep_agent": ("health_trend", "health_profile", "knowledge_search"),
            "risk_agent": ("risk_tool", "health_trend", "health_profile", "report_tool"),
            "mental_health_agent": ("mental_health_trend", "mental_assessment", "knowledge_search"),
            "health_plan_agent": ("health_profile", "health_trend", "risk_tool"),
        }
        for code, names in candidates.items():
            rows = (await session.execute(select(Tool).where(Tool.name.in_(names), Tool.status == "active"))).scalars().all()
            if rows:
                existing[code].config = {**(existing[code].config or {}), "tools": {"enabled": True, "tool_ids": [str(t.id) for t in rows[:10]], "max_iterations": 5}}

        await session.commit()
        for code, agent in existing.items():
            print(f"{code}={agent.id}")


if __name__ == "__main__":
    asyncio.run(main())
