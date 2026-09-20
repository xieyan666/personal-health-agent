from uuid import UUID, uuid4

import pytest

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.models import Agent, AgentRun, Conversation, Message, ModelConfig, ModelProvider, User


@pytest.mark.asyncio
async def test_stream_runtime_persists_only_final_assistant(service_context):
    session, track = service_context
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"stream-{suffix}", display_name="Stream", email=f"stream-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"stream-provider-{suffix}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"stream-config-{suffix}", model_name="fake-chat", model_type="chat", status="active", parameters={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"stream-{suffix}", name="Stream", category="test", status="active", model_config_id=config.id, config={}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, agent, conversation]); await session.commit()
    events = [event async for event in AgentRuntimeService(session).stream_run(user.id, agent.id, conversation.id, "hello")]
    assert [event["type"] for event in events] == ["run_started", "message_delta", "message_delta", "run_completed"]
    completed = events[-1]
    run = track(await session.get(AgentRun, UUID(completed["run_id"])))
    assistant = track(await session.get(Message, UUID(completed["assistant_message_id"])))
    for message in await AgentRuntimeService(session).messages.list_messages(conversation.id):
        track(message)
    assert run.status == "succeeded" and run.output_message_id == assistant.id
    assert assistant.content == "Fake assistant response: hello"


@pytest.mark.asyncio
async def test_stream_provider_error_marks_run_failed_without_assistant(service_context, monkeypatch):
    session, track = service_context
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"stream-error-{suffix}", display_name="Stream", email=f"stream-error-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"stream-error-provider-{suffix}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"stream-error-config-{suffix}", model_name="fake-chat", model_type="chat", status="active", parameters={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"stream-error-{suffix}", name="Stream", category="test", status="active", model_config_id=config.id, config={}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, agent, conversation]); await session.commit()

    class BrokenProvider:
        async def stream_chat(self, *_args, **_kwargs):
            raise RuntimeError("broken")
            yield

    monkeypatch.setattr("backend.app.agent.runtime.chat_provider_for", lambda *_args, **_kwargs: BrokenProvider())
    events = [event async for event in AgentRuntimeService(session).stream_run(user.id, agent.id, conversation.id, "hello")]
    assert events[-1]["type"] == "error"
    run = track(await session.get(AgentRun, UUID(events[0]["run_id"])))
    assert run.status == "failed" and run.output_message_id is None
    for message in await AgentRuntimeService(session).messages.list_messages(conversation.id):
        track(message)
    assert [message.role for message in await AgentRuntimeService(session).messages.list_messages(conversation.id)] == ["user"]
