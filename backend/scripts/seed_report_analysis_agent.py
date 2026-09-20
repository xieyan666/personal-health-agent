"""Register the AI Report Agent on the platform agents table (idempotent).

The Report Agent is a system-scoped agent used for trace recording when the
health report interpretation endpoint runs.  Run with:

    python -m scripts.seed_report_analysis_agent
"""

import asyncio
from sqlalchemy import select
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Agent, ModelConfig, ModelProvider

AGENT_CODE = "health_report_interpretation"
AGENT_NAME = "Report Agent"
AGENT_CATEGORY = "health"
AGENT_DESCRIPTION = (
    "读取已解析体检报告的结构化指标与用户健康档案，"
    "调用 DeepSeek 生成结构化健康管理解读，并经过 Safety Guard 校验。"
)


async def main() -> None:
    async with AsyncSessionFactory() as session:
        existing = await session.scalar(select(Agent).where(Agent.code == AGENT_CODE))
        # Prefer an active chat model config backed by the deepseek provider.
        deepseek_config = await session.scalar(
            select(ModelConfig)
            .join(ModelProvider, ModelProvider.id == ModelConfig.provider_id)
            .where(
                ModelConfig.status == "active",
                ModelConfig.model_type == "chat",
                ModelProvider.provider_type == "deepseek",
            )
            .order_by(ModelConfig.created_at.desc())
            .limit(1)
        )
        model_config_id = deepseek_config.id if deepseek_config is not None else None
        if existing is not None:
            existing.status = "active"
            existing.name = AGENT_NAME
            existing.description = AGENT_DESCRIPTION
            if model_config_id is not None:
                existing.model_config_id = model_config_id
            print(f"Updated existing Report Agent: {existing.id}")
        else:
            agent = Agent(
                scope="system",
                code=AGENT_CODE,
                name=AGENT_NAME,
                category=AGENT_CATEGORY,
                description=AGENT_DESCRIPTION,
                status="active",
                model_config_id=model_config_id,
                config={},
            )
            session.add(agent)
            await session.flush()
            print(f"Created Report Agent: {agent.id}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
