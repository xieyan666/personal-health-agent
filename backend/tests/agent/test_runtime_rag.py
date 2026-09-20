from uuid import UUID, uuid4

import pytest

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.exceptions import NotFoundError, ValidationError
from backend.app.model_gateway.chat import ChatResult, FakeChatProvider
from backend.app.models import Agent, AgentRun, Conversation, Message, ModelConfig, ModelProvider, User
from backend.app.services.rag import RagContext


async def _setup(session, track, rag_config):
    suffix = uuid4().hex
    user = track(User(id=uuid4(), username=f"rag-{suffix}", display_name="RAG", email=f"rag-{suffix}@example.com", auth_source="local"))
    provider = track(ModelProvider(id=uuid4(), name=f"rag-provider-{suffix}", provider_type="fake", status="active", config={}))
    config = track(ModelConfig(id=uuid4(), provider_id=provider.id, name=f"rag-config-{suffix}", model_name="fake-chat", model_type="chat", status="active", parameters={}))
    agent = track(Agent(id=uuid4(), owner_user_id=user.id, scope="personal", code=f"rag-{suffix}", name="RAG", category="test", status="active", model_config_id=config.id, config=rag_config))
    conversation = track(Conversation(id=uuid4(), user_id=user.id, agent_id=agent.id, status="active", context={}))
    session.add_all([user, provider, config, agent, conversation]); await session.commit()
    return user, agent, conversation


@pytest.mark.asyncio
async def test_rag_disabled_preserves_runtime_and_stream(service_context):
    session, track = service_context
    user, agent, conversation = await _setup(session, track, {})
    service = AgentRuntimeService(session)
    result = await service.run(user.id, agent.id, conversation.id, "hello")
    assert result.assistant_content == "Fake assistant response: hello"
    track(await service.runs.get_agent_run(result.run_id))
    track(await service.messages.get_message(result.user_message_id))
    track(await service.messages.get_message(result.assistant_message_id))
    stream = [event async for event in service.stream_run(user.id, agent.id, conversation.id, "again")]
    assert stream[0]["type"] == "run_started" and stream[-1]["type"] == "run_completed"
    track(await service.runs.get_agent_run(UUID(stream[0]["run_id"])))
    for message in await service.messages.list_messages(conversation.id):
        track(message)


@pytest.mark.asyncio
async def test_rag_context_injected_without_persisting_context(service_context, monkeypatch):
    session, track = service_context
    rag = {"rag": {"enabled": True, "knowledge_base_id": str(uuid4()), "embedding_model_config_id": str(uuid4()), "top_k": 3}}
    user, agent, conversation = await _setup(session, track, rag)
    captured = []

    class CapturingProvider:
        def chat(self, messages, **kwargs):
            captured.extend(messages)
            return ChatResult("answer", kwargs["model_name"], 1, 1, 2)

    async def build_context(*args, **kwargs):
        assert args[-1] == 3
        return RagContext(args[0], args[1], [], "company policy context")

    monkeypatch.setattr("backend.app.agent.runtime.RagService.build_context", build_context)
    monkeypatch.setattr("backend.app.agent.runtime.chat_provider_for", lambda *_args, **_kwargs: CapturingProvider())
    result = await AgentRuntimeService(session).run(user.id, agent.id, conversation.id, "question")
    assert result.assistant_content == "answer"
    assert captured[0].role == "system" and "company policy context" in captured[0].content
    messages = await AgentRuntimeService(session).messages.list_messages(conversation.id)
    track(await AgentRuntimeService(session).runs.get_agent_run(result.run_id))
    for message in messages:
        track(message)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert all("company policy context" not in message.content for message in messages)


@pytest.mark.asyncio
async def test_rag_empty_result_still_calls_fake_stream(service_context, monkeypatch):
    session, track = service_context
    rag = {"rag": {"enabled": True, "knowledge_base_id": str(uuid4()), "embedding_model_config_id": str(uuid4()), "top_k": 5}}
    user, agent, conversation = await _setup(session, track, rag)

    async def empty_context(*args, **kwargs):
        return RagContext(args[0], args[1], [], "")

    monkeypatch.setattr("backend.app.agent.runtime.RagService.build_context", empty_context)
    events = [event async for event in AgentRuntimeService(session).stream_run(user.id, agent.id, conversation.id, "hello")]
    assert events[-1]["type"] == "run_completed"
    assert all("KNOWLEDGE_CONTEXT" not in str(event) for event in events)
    run = await AgentRuntimeService(session).runs.get_agent_run(UUID(events[0]["run_id"]))
    track(run)
    for message in await AgentRuntimeService(session).messages.list_messages(conversation.id):
        track(message)


@pytest.mark.asyncio
async def test_rag_failure_marks_run_failed_without_assistant(service_context, monkeypatch):
    session, track = service_context
    rag = {"rag": {"enabled": True, "knowledge_base_id": str(uuid4()), "embedding_model_config_id": str(uuid4())}}
    user, agent, conversation = await _setup(session, track, rag)

    async def failing_context(*args, **kwargs):
        raise NotFoundError("Knowledge base not found")

    monkeypatch.setattr("backend.app.agent.runtime.RagService.build_context", failing_context)
    events = [event async for event in AgentRuntimeService(session).stream_run(user.id, agent.id, conversation.id, "hello")]
    assert events[-1]["type"] == "error"
    run = await AgentRuntimeService(session).runs.get_agent_run(UUID(events[0]["run_id"]))
    track(run)
    assert run.status == "failed" and run.output_message_id is None
    messages = await AgentRuntimeService(session).messages.list_messages(conversation.id)
    for message in messages:
        track(message)
    assert [message.role for message in messages] == ["user"]
