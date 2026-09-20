import asyncio
import socket
import subprocess
import sys
from uuid import UUID, uuid4
import pytest
from backend.app.agent.runtime import AgentRuntimeService
from backend.app.models import Agent, Conversation, ModelConfig, ModelProvider, Tool, User
from backend.app.services.rag import RagContext


async def _wait_port():
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=.2): return
        except OSError: await asyncio.sleep(.1)
    raise RuntimeError("HTTP MCP server did not start")


@pytest.mark.asyncio
async def test_rag_and_mcp_runtime_nonstream_and_stream(service_context, monkeypatch):
    process = subprocess.Popen([sys.executable, "backend/tests/mcp/fixtures/http_server.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await _wait_port(); session, track = service_context; tag = uuid4().hex
        user = User(id=uuid4(), username=f"mcp-46d-{tag}", display_name="MCP", email=f"mcp-46d-{tag}@example.com", auth_source="local")
        chat_provider = ModelProvider(id=uuid4(), name=f"mcp-chat-{tag}", provider_type="fake", status="active", config={})
        chat_config = ModelConfig(id=uuid4(), provider_id=chat_provider.id, name=f"mcp-chat-config-{tag}", model_name="fake", model_type="chat", status="active", parameters={})
        tool = Tool(id=uuid4(), name=f"mcp_rag_add_{tag}", display_name="Add", tool_type="mcp", implementation_ref=f"mcp-rag:{tag}", status="active", risk_level="low", requires_approval=False, input_schema={"type":"object"}, config={"server":{"transport":"streamable_http","url":"http://127.0.0.1:8765/mcp","allow_private_network":True},"remote_tool_name":"add_numbers","server_alias":"rag_test"})
        agent = Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"mcp-rag-agent-{tag}", name="RAG MCP", category="test", status="active", model_config_id=chat_config.id, config={"rag":{"enabled":True,"knowledge_base_id":str(uuid4()),"embedding_model_config_id":str(uuid4()),"top_k":3},"tools":{"enabled":True,"tool_ids":[str(tool.id)],"max_iterations":3}})
        conversation = Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={})
        session.add_all([user, chat_provider, chat_config, tool, agent, conversation]); await session.commit()
        for item in (user, chat_provider, chat_config, tool, agent, conversation): track(item)
        calls = 0
        async def context(*args, **kwargs):
            nonlocal calls; calls += 1
            return RagContext(args[0], args[1], [], "PH-MCP-46D 的基础分值为 17，需要额外增加 25。")
        monkeypatch.setattr("backend.app.agent.runtime.RagService.build_context", context)
        runtime = AgentRuntimeService(session)
        result = await runtime.run(user.id, agent.id, conversation.id, "根据知识库信息，使用 add_numbers 计算最终分值")
        assert result.run_status == "succeeded" and "42" in result.assistant_content and calls == 1
        for message in await runtime.messages.list_messages(conversation.id): track(message)
        track(await runtime.runs.get_agent_run(result.run_id))
        events = [event async for event in runtime.stream_run(user.id, agent.id, conversation.id, "根据知识库信息，使用 add_numbers 计算最终分值")]
        assert events[0]["type"] == "run_started" and events[-1]["type"] == "run_completed"
        assert any(event["type"] == "tool_call_completed" for event in events)
        assert all("url" not in event and "headers" not in event and "result" not in event for event in events)
        for message in await runtime.messages.list_messages(conversation.id): track(message)
        track(await runtime.runs.get_agent_run(UUID(events[0]["run_id"])))
    finally:
        process.terminate(); process.wait(timeout=5)
