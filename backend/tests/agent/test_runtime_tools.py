from uuid import UUID, uuid4
import pytest
from backend.app.agent.runtime import AgentRuntimeService
from backend.app.models import Agent, Conversation, ModelConfig, ModelProvider, Tool, User

SCHEMA = {"type": "object", "properties": {"weight_kg": {"type": "number"}, "height_cm": {"type": "number"}}, "required": ["weight_kg", "height_cm"], "additionalProperties": False}

async def setup_tool_runtime(session, track, enabled=True, parameters=None):
    tag = uuid4().hex
    user = track(User(id=uuid4(), username=f"tool-{tag}", display_name="Tool", email=f"tool-{tag}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"tool-provider-{tag}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"tool-config-{tag}", model_name="fake", model_type="chat", status="active", parameters=parameters or {}))
    repository = __import__('backend.app.repositories.tool', fromlist=['ToolRepository']).ToolRepository(session)
    tool = await repository.get_by_name("calculate_bmi")
    if tool is None:
        tool = track(Tool(id=uuid4(), name="calculate_bmi", display_name="BMI", tool_type="builtin", implementation_ref=f"builtin:{tag}", status="active", risk_level="low", requires_approval=False, input_schema=SCHEMA, config={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"tool-{tag}", name="Tool", category="test", status="active", model_config_id=config.id, config={"tools": {"enabled": enabled, "tool_ids": [str(tool.id)], "max_iterations": 3}} if enabled else {}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, tool, agent, conversation]); await session.commit()
    return user, agent, conversation

@pytest.mark.asyncio
async def test_runtime_tool_loop_persists_only_user_and_final_assistant(service_context):
    session, track = service_context
    user, agent, conversation = await setup_tool_runtime(session, track)
    runtime = AgentRuntimeService(session)
    result = await runtime.run(user.id, agent.id, conversation.id, "请使用 calculate_bmi 工具计算 70kg、175cm 的 BMI")
    assert result.run_status == "succeeded" and "22.86" in result.assistant_content
    run = track(await runtime.runs.get_agent_run(result.run_id))
    messages = await runtime.messages.list_messages(conversation.id)
    for message in messages: track(message)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert run.output_message_id == result.assistant_message_id
    assert run.prompt_tokens > 0 and run.completion_tokens > 0 and run.latency_ms >= 0

@pytest.mark.asyncio
async def test_stream_tool_loop_emits_safe_events_and_single_assistant(service_context):
    session, track = service_context
    user, agent, conversation = await setup_tool_runtime(session, track)
    runtime = AgentRuntimeService(session)
    events = [event async for event in runtime.stream_run(user.id, agent.id, conversation.id, "请使用 calculate_bmi 工具计算 70kg、175cm 的 BMI")]
    types = [event["type"] for event in events]
    assert types[0] == "run_started" and "tool_call_started" in types and "tool_call_completed" in types and "message_delta" in types and types[-1] == "run_completed"
    assert all("arguments" not in event and "result" not in event for event in events)
    run = track(await runtime.runs.get_agent_run(UUID(events[0]["run_id"])))
    messages = await runtime.messages.list_messages(conversation.id)
    for message in messages: track(message)
    assert run.status == "succeeded" and [message.role for message in messages] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_tool_runtime_rejects_insufficient_token_budget(service_context):
    session, track = service_context
    user, agent, conversation = await setup_tool_runtime(session, track, parameters={"max_tokens": 128})
    runtime = AgentRuntimeService(session)
    with pytest.raises(Exception, match="TOOL_TOKEN_BUDGET_TOO_SMALL"):
        await runtime.run(user.id, agent.id, conversation.id, "请使用 calculate_bmi 工具计算 70kg、175cm 的 BMI")
    runs = await runtime.runs.repository.list_by_conversation_id(conversation.id)
    for run in runs:
        track(run)
    for message in await runtime.messages.list_messages(conversation.id):
        track(message)
    assert runs[-1].status == "failed" and runs[-1].output_message_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("parameters", [{"max_tokens": 256}, {"max_tokens": 512}, {}])
async def test_tool_runtime_accepts_safe_or_default_token_budget(service_context, parameters):
    session, track = service_context
    user, agent, conversation = await setup_tool_runtime(session, track, parameters=parameters)
    runtime = AgentRuntimeService(session)
    result = await runtime.run(user.id, agent.id, conversation.id, "请使用 calculate_bmi 工具计算 70kg、175cm 的 BMI")
    track(await runtime.runs.get_agent_run(result.run_id))
    for message in await runtime.messages.list_messages(conversation.id):
        track(message)
    assert result.run_status == "succeeded"


@pytest.mark.asyncio
async def test_stream_truncated_tool_call_fails_without_executor_or_assistant(service_context, monkeypatch):
    session, track = service_context
    user, agent, conversation = await setup_tool_runtime(session, track, parameters={"max_tokens": 256})
    executed = False

    class TruncatedProvider:
        async def stream_chat(self, *_args, **_kwargs):
            raise __import__("backend.app.exceptions", fromlist=["ValidationError"]).ValidationError("TOOL_CALL_TRUNCATED")
            yield

    async def should_not_execute(*_args, **_kwargs):
        nonlocal executed
        executed = True

    monkeypatch.setattr("backend.app.agent.runtime.chat_provider_for", lambda *_args, **_kwargs: TruncatedProvider())
    runtime = AgentRuntimeService(session)
    monkeypatch.setattr(runtime.tool_executor, "execute", should_not_execute)
    events = [event async for event in runtime.stream_run(user.id, agent.id, conversation.id, "请使用 calculate_bmi 工具计算 70kg、175cm 的 BMI")]
    run = track(await runtime.runs.get_agent_run(UUID(events[0]["run_id"])))
    for message in await runtime.messages.list_messages(conversation.id):
        track(message)
    assert events[-1]["type"] == "error"
    assert run.status == "failed" and run.output_message_id is None and executed is False
