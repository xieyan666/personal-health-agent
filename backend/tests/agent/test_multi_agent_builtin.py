from uuid import uuid4
import pytest
from sqlalchemy import select

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.models import Agent, Conversation, ModelConfig, ModelProvider, Tool, User


@pytest.mark.asyncio
async def test_sub_agent_builtin_tool_runs_without_internal_messages(service_context):
    session, track = service_context; tag = uuid4().hex
    user = User(id=uuid4(), username=f"multi-agent-47-{tag}", display_name="MA", email=f"multi-agent-47-{tag}@example.com", auth_source="local")
    provider = ModelProvider(id=uuid4(), name=f"multi-agent-provider-{tag}", provider_type="fake", status="active", config={})
    config = ModelConfig(id=uuid4(), provider_id=provider.id, name=f"multi-agent-config-{tag}", model_name="fake", model_type="chat", status="active", parameters={})
    tool = (await session.execute(select(Tool).where(Tool.name == "calculate_bmi"))).scalars().one()
    child = Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-health-{tag}", name="Health", category="test", status="active", model_config_id=config.id, config={"tools":{"enabled":True,"tool_ids":[str(tool.id)],"max_iterations":3}})
    root = Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-root-{tag}", name="Coordinator", category="test", status="active", model_config_id=config.id, config={"multi_agent":{"enabled":True,"sub_agent_ids":[str(child.id)]}})
    conversation = Conversation(id=uuid4(), user_id=user.id, agent_id=root.id, status="active", context={})
    session.add_all([user, provider, config, root, child, conversation]); await session.commit()
    for item in (user, provider, config, root, child, conversation): track(item)
    runtime = AgentRuntimeService(session)
    result = await runtime.run(user.id, root.id, conversation.id, "请使用 calculate_bmi 计算 70kg 和 175cm")
    assert result.run_status == "succeeded" and "22.86" in result.assistant_content
    runs = await runtime.runs.list_agent_runs(conversation_id=conversation.id, limit=10)
    assert any(item.agent_id == child.id and item.status == "succeeded" for item in runs)
    messages = await runtime.messages.list_messages(conversation.id)
    assert [item.role for item in messages] == ["user", "assistant"]
    for item in [*runs, *messages]: track(item)
