import asyncio
import socket
import subprocess
import sys
from uuid import uuid4
import pytest
from backend.app.agent.runtime import AgentRuntimeService
from backend.app.models import Agent, Conversation, ModelConfig, ModelProvider, Tool, User


async def _wait_port():
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=.2): return
        except OSError: await asyncio.sleep(.1)
    raise RuntimeError("HTTP MCP server did not start")


@pytest.mark.asyncio
async def test_runtime_http_mcp_loop(service_context):
    process = subprocess.Popen([sys.executable, "backend/tests/mcp/fixtures/http_server.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await _wait_port()
        session, track = service_context; tag = uuid4().hex
        user = User(id=uuid4(), username=f"mcp-http-{tag}", display_name="MCP", email=f"mcp-http-{tag}@example.com", auth_source="local")
        provider = ModelProvider(id=uuid4(), name=f"mcp-http-provider-{tag}", provider_type="fake", status="active", config={})
        config = ModelConfig(id=uuid4(), provider_id=provider.id, name=f"mcp-http-config-{tag}", model_name="fake", model_type="chat", status="active", parameters={})
        tool = Tool(id=uuid4(), name=f"mcp_http_add_{tag}", display_name="Add", tool_type="mcp", implementation_ref=f"mcp-http:{tag}", status="active", risk_level="low", requires_approval=False, input_schema={"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}, config={"server":{"transport":"streamable_http","url":"http://127.0.0.1:8765/mcp","allow_private_network":True},"remote_tool_name":"add_numbers","server_alias":"http_test"})
        agent = Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"mcp-http-agent-{tag}", name="MCP", category="test", status="active", model_config_id=config.id, config={"tools":{"enabled":True,"tool_ids":[str(tool.id)],"max_iterations":3}})
        conversation = Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={})
        session.add_all([user, provider, config, tool, agent, conversation]); await session.commit()
        for item in (user, provider, config, tool, agent, conversation): track(item)
        result = await AgentRuntimeService(session).run(user.id, agent.id, conversation.id, "请使用 add_numbers 计算 2 + 3")
        assert result.run_status == "succeeded" and "5" in result.assistant_content
        runtime = AgentRuntimeService(session)
        for message in await runtime.messages.list_messages(conversation.id): track(message)
        track(await runtime.runs.get_agent_run(result.run_id))
    finally:
        process.terminate(); process.wait(timeout=5)
