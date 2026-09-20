from uuid import uuid4
import pytest

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.models import Agent, Conversation, ModelConfig, ModelProvider, Tool, User


@pytest.mark.asyncio
async def test_sub_agent_mcp_uses_root_conversation_and_child_run(service_context):
    session, track = service_context; tag = uuid4().hex
    user = User(id=uuid4(), username=f"multi-agent-47-{tag}", display_name="MA", email=f"multi-agent-47-{tag}@example.com", auth_source="local")
    provider = ModelProvider(id=uuid4(), name=f"multi-agent-provider-{tag}", provider_type="fake", status="active", config={})
    config = ModelConfig(id=uuid4(), provider_id=provider.id, name=f"multi-agent-config-{tag}", model_name="fake", model_type="chat", status="active", parameters={})
    tool = Tool(id=uuid4(), name=f"multi-agent-add-{tag}", display_name="Add", tool_type="mcp", implementation_ref=f"mcp:multi-agent-{tag}", status="active", risk_level="low", requires_approval=False, input_schema={"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}, config={"server":{"transport":"stdio","command":"python","args":["backend/tests/mcp/fixtures/test_server.py"]},"remote_tool_name":"add_numbers","server_alias":"multi_agent"})
    child = Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-child-{tag}", name="Calculation", category="test", status="active", model_config_id=config.id, config={"tools":{"enabled":True,"tool_ids":[str(tool.id)],"max_iterations":3}})
    root = Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"multi-agent-root-{tag}", name="Coordinator", category="test", status="active", model_config_id=config.id, config={"multi_agent":{"enabled":True,"sub_agent_ids":[str(child.id)],"max_handoffs":3}})
    conversation = Conversation(id=uuid4(), user_id=user.id, agent_id=root.id, status="active", context={})
    session.add_all([user, provider, config, tool, root, child, conversation]); await session.commit()
    for item in (user, provider, config, tool, root, child, conversation): track(item)
    runtime = AgentRuntimeService(session)
    result = await runtime.run(user.id, root.id, conversation.id, "请使用 add_numbers 计算最终分值")
    assert result.run_status == "succeeded" and "42" in result.assistant_content
    runs = await runtime.runs.list_agent_runs(conversation_id=conversation.id, limit=10)
    child_runs = [item for item in runs if item.agent_id == child.id]
    assert len(child_runs) == 1 and child_runs[0].status == "succeeded" and child_runs[0].conversation_id == conversation.id
    messages = await runtime.messages.list_messages(conversation.id)
    assert [item.role for item in messages] == ["user", "assistant"]
    for item in [*runs, *messages]: track(item)
