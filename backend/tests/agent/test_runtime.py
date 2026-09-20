from uuid import uuid4

import pytest

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.exceptions import ServiceError
from backend.app.models import Agent, AgentRun, Conversation, Message, ModelConfig, ModelProvider, User
from backend.app.services.exceptions import NotFoundError, ValidationError


@pytest.mark.asyncio
async def test_runtime_validates_missing_user(service_context):
    session, _ = service_context
    with pytest.raises(NotFoundError):
        await AgentRuntimeService(session).run(uuid4(), uuid4(), uuid4(), "hello")


@pytest.mark.asyncio
async def test_runtime_executes_persisted_message_flow(service_context):
    session, track = service_context
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"runtime-{suffix}", display_name="Runtime", email=f"runtime-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"provider-{suffix}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"chat-{suffix}", model_name="fake-chat", model_type="chat", status="active", parameters={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"runtime-{suffix}", name="Runtime", category="test", status="active", model_config_id=config.id, config={}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, agent, conversation]); await session.commit()
    result = await AgentRuntimeService(session).run(user.id, agent.id, conversation.id, "hello")
    assert result.run_status == "succeeded"
    assert result.assistant_content == "Fake assistant response: hello"
    run = await AgentRuntimeService(session).runs.get_agent_run(result.run_id)
    track(run)
    track(await session.get(Message, result.user_message_id))
    track(await session.get(Message, result.assistant_message_id))
    assert run.output_message_id == result.assistant_message_id
    assert run.status == "succeeded"
    assert run.prompt_tokens > 0
    assert run.completion_tokens > 0


@pytest.mark.asyncio
async def test_runtime_marks_run_failed_without_assistant_when_provider_fails(service_context, monkeypatch):
    session, track = service_context
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"runtime-fail-{suffix}", display_name="Runtime", email=f"runtime-fail-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"provider-fail-{suffix}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"chat-fail-{suffix}", model_name="fake-chat", model_type="chat", status="active", parameters={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"runtime-fail-{suffix}", name="Runtime", category="test", status="active", model_config_id=config.id, config={}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, agent, conversation]); await session.commit()

    class FailingProvider:
        def chat(self, *_args, **_kwargs):
            raise ServiceError("provider unavailable")

    monkeypatch.setattr("backend.app.agent.runtime.chat_provider_for", lambda *_args, **_kwargs: FailingProvider())
    with pytest.raises(ServiceError, match="provider unavailable"):
        await AgentRuntimeService(session).run(user.id, agent.id, conversation.id, "hello")

    runs = await AgentRuntimeService(session).runs.list_agent_runs(conversation_id=conversation.id)
    assert len(runs) == 1
    run = track(runs[0])
    assert run.status == "failed"
    assert run.output_message_id is None
    messages = await AgentRuntimeService(session).messages.list_messages(conversation.id)
    for message in messages:
        track(message)
    assert [message.role for message in messages] == ["user"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "model_type", "config_status"),
    [("inactive", "chat", "active"), ("active", "embedding", "active"), ("active", "chat", "inactive")],
)
async def test_runtime_rejects_unavailable_chat_configuration(service_context, provider_status, model_type, config_status):
    session, track = service_context
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"runtime-config-{suffix}", display_name="Runtime", email=f"runtime-config-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"provider-config-{suffix}", provider_type="fake", status=provider_status, config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"config-{suffix}", model_name="fake-chat", model_type=model_type, status=config_status, parameters={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"runtime-config-{suffix}", name="Runtime", category="test", status="active", model_config_id=config.id, config={}))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, agent, conversation]); await session.commit()
    with pytest.raises(ValidationError):
        await AgentRuntimeService(session).run(user.id, agent.id, conversation.id, "hello")
