"""Real PostgreSQL tests for core business Services."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Agent, User
from backend.app.services import (
    AgentRunService,
    AgentService,
    AuditLogService,
    ConflictError,
    ConversationService,
    DocumentService,
    KnowledgeBaseService,
    MessageService,
    ModelConfigService,
    ModelProviderService,
    NotFoundError,
    ToolService,
    UserService,
    ValidationError,
)


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def user_values(**overrides: object) -> dict:
    values = {
        "username": unique("user"),
        "display_name": "Service User",
        "email": f"{uuid4().hex}@example.test",
        "auth_source": "local",
        "password_hash": "test-hash",
        "status": "active",
        "timezone": "Asia/Shanghai",
    }
    values.update(overrides)
    return values


def agent_values(**overrides: object) -> dict:
    values = {
        "owner_user_id": None,
        "scope": "system",
        "code": unique("agent"),
        "name": "Service Agent",
        "category": "daily_health",
        "status": "active",
        "config": {},
        "version": 1,
    }
    values.update(overrides)
    return values


def message_values(conversation_id: object, **overrides: object) -> dict:
    values = {
        "conversation_id": conversation_id,
        "role": "user",
        "content": "service message",
        "content_data": {},
        "status": "completed",
        "source_type": "user",
        "source_reference": {},
        "risk_level": "low",
        "safety_status": "passed",
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_user_service_rules_commit_rollback_and_crud(service_context: tuple) -> None:
    session, track = service_context
    service = UserService(session)
    external_id = unique("employee")
    user = track(
        await service.create_user(
            **user_values(
                auth_source="oidc",
                external_user_id=external_id,
                password_hash=None,
            )
        )
    )
    user_id, username = user.id, user.username

    async with AsyncSessionFactory() as independent:
        assert await independent.get(User, user_id) is not None

    with pytest.raises(ConflictError):
        await service.create_user(**user_values(username=username))
    with pytest.raises(ConflictError):
        await service.create_user(
            **user_values(
                auth_source="oidc",
                external_user_id=external_id,
                password_hash=None,
            )
        )
    with pytest.raises(NotFoundError):
        await service.get_user(uuid4())

    updated = await service.update_user(user_id, display_name="Updated Service User")
    assert updated.display_name == "Updated Service User"
    deletable = track(await service.create_user(**user_values()))
    deletable_id = deletable.id
    await service.delete_user(deletable_id)
    with pytest.raises(NotFoundError):
        await service.get_user(deletable_id)

    invalid_code = unique("invalid_scope")
    with pytest.raises(ValidationError):
        await AgentService(session).create_agent(
            **agent_values(code=invalid_code, scope="invalid")
        )
    async with AsyncSessionFactory() as independent:
        assert await independent.scalar(
            select(Agent).where(Agent.code == invalid_code)
        ) is None


@pytest.mark.asyncio
async def test_model_and_agent_service_rules(service_context: tuple) -> None:
    session, track = service_context
    users = UserService(session)
    providers = ModelProviderService(session)
    configs = ModelConfigService(session)
    agents = AgentService(session)
    user = track(await users.create_user(**user_values()))
    user_id = user.id
    provider_name = unique("provider")
    provider = track(
        await providers.create_provider(
            name=provider_name, provider_type="llm", status="active", config={}
        )
    )
    provider_id = provider.id
    with pytest.raises(ConflictError):
        await providers.create_provider(
            name=provider_name, provider_type="llm", status="active", config={}
        )
    config = track(
        await configs.create_model_config(
            provider_id=provider_id,
            name=unique("config"),
            model_name="test-model",
            model_type="chat",
            status="active",
            parameters={},
        )
    )
    config_id = config.id
    with pytest.raises(NotFoundError):
        await configs.create_model_config(
            provider_id=uuid4(),
            name=unique("config"),
            model_name="missing",
            model_type="chat",
            status="active",
            parameters={},
        )

    system = track(await agents.create_agent(**agent_values()))
    personal = track(
        await agents.create_agent(
            **agent_values(
                scope="personal", owner_user_id=user_id, model_config_id=config_id
            )
        )
    )
    system_id, personal_id = system.id, personal.id
    system_code = system.code
    assert system.owner_user_id is None and personal.owner_user_id == user_id
    with pytest.raises(ValidationError):
        await agents.create_agent(**agent_values(scope="personal"))
    with pytest.raises(NotFoundError):
        await agents.create_agent(
            **agent_values(scope="personal", owner_user_id=uuid4())
        )
    with pytest.raises(NotFoundError):
        await agents.create_agent(**agent_values(model_config_id=uuid4()))
    with pytest.raises(ConflictError):
        await agents.create_agent(**agent_values(code=system_code))
    with pytest.raises(ValidationError):
        await agents.update_agent(system_id, scope="invalid")
    with pytest.raises(ValidationError):
        await agents.update_agent(personal_id, owner_user_id=None)
    with pytest.raises(ValidationError):
        await agents.update_agent(system_id, scope="personal")


@pytest.mark.asyncio
async def test_conversation_and_message_service_rules(service_context: tuple) -> None:
    session, track = service_context
    user = track(await UserService(session).create_user(**user_values()))
    agent = track(await AgentService(session).create_agent(**agent_values()))
    user_id, agent_id = user.id, agent.id
    conversations = ConversationService(session)
    messages = MessageService(session)
    first_conversation = track(
        await conversations.create_conversation(
            user_id=user_id,
            agent_id=agent_id,
            title="First",
            status="active",
            context={},
        )
    )
    second_conversation = track(
        await conversations.create_conversation(
            user_id=user_id,
            agent_id=agent_id,
            title="Second",
            status="active",
            context={},
        )
    )
    first_id, second_id = first_conversation.id, second_conversation.id
    with pytest.raises(NotFoundError):
        await conversations.create_conversation(
            user_id=uuid4(), agent_id=agent_id, status="active", context={}
        )
    with pytest.raises(NotFoundError):
        await conversations.create_conversation(
            user_id=user_id, agent_id=uuid4(), status="active", context={}
        )

    parent = track(await messages.create_message(**message_values(first_id)))
    child = track(
        await messages.create_message(
            **message_values(first_id, parent_message_id=parent.id, role="assistant")
        )
    )
    foreign_parent = track(await messages.create_message(**message_values(second_id)))
    foreign_parent_id = foreign_parent.id
    assert child.parent_message_id == parent.id
    with pytest.raises(NotFoundError):
        await messages.create_message(**message_values(uuid4()))
    with pytest.raises(ValidationError):
        await messages.create_message(
            **message_values(first_id, parent_message_id=foreign_parent_id)
        )


@pytest.mark.asyncio
async def test_knowledge_document_and_tool_service_rules(service_context: tuple) -> None:
    session, track = service_context
    user = track(await UserService(session).create_user(**user_values()))
    user_id = user.id
    knowledge = KnowledgeBaseService(session)
    documents = DocumentService(session)
    tools = ToolService(session)
    kb = track(
        await knowledge.create_knowledge_base(
            owner_user_id=user_id,
            name="Service KB",
            status="active",
            index_version=1,
            retrieval_config={},
        )
    )
    kb_id = kb.id
    with pytest.raises(NotFoundError):
        await knowledge.create_knowledge_base(
            owner_user_id=uuid4(),
            name="Missing Owner",
            status="active",
            index_version=1,
            retrieval_config={},
        )
    with pytest.raises(ConflictError):
        await knowledge.create_knowledge_base(
            owner_user_id=user_id,
            name="Service KB",
            status="active",
            index_version=1,
            retrieval_config={},
        )
    document = track(
        await documents.create_document(
            knowledge_base_id=kb_id,
            name="test.txt",
            source_type="upload",
            source_reference={},
            status="ready",
            metadata_={},
        )
    )
    assert document.knowledge_base_id == kb_id
    with pytest.raises(NotFoundError):
        await documents.create_document(
            knowledge_base_id=uuid4(),
            name="missing.txt",
            source_type="upload",
            source_reference={},
            status="ready",
            metadata_={},
        )

    tool_name, implementation = unique("tool"), unique("builtin:tool")
    tool = track(
        await tools.create_tool(
            name=tool_name,
            display_name="Tool",
            tool_type="builtin",
            implementation_ref=implementation,
            status="active",
            risk_level="low",
            requires_approval=False,
            input_schema={},
            config={},
        )
    )
    tool_id = tool.id
    with pytest.raises(ConflictError):
        await tools.create_tool(
            name=tool_name,
            display_name="Duplicate",
            tool_type="builtin",
            implementation_ref=unique("impl"),
            status="active",
            risk_level="low",
            requires_approval=False,
            input_schema={},
            config={},
        )
    with pytest.raises(ConflictError):
        await tools.create_tool(
            name=unique("tool"),
            display_name="Duplicate",
            tool_type="builtin",
            implementation_ref=implementation,
            status="active",
            risk_level="low",
            requires_approval=False,
            input_schema={},
            config={},
        )
    assert (await tools.get_tool(tool_id)).id == tool_id


@pytest.mark.asyncio
async def test_agent_run_service_rules(service_context: tuple) -> None:
    session, track = service_context
    user = track(await UserService(session).create_user(**user_values()))
    agent = track(await AgentService(session).create_agent(**agent_values()))
    conversations = ConversationService(session)
    first = track(
        await conversations.create_conversation(
            user_id=user.id, agent_id=agent.id, status="active", context={}
        )
    )
    second = track(
        await conversations.create_conversation(
            user_id=user.id, agent_id=agent.id, status="active", context={}
        )
    )
    first_id, second_id, agent_id, user_id = first.id, second.id, agent.id, user.id
    messages = MessageService(session)
    trigger = track(await messages.create_message(**message_values(first_id)))
    foreign = track(await messages.create_message(**message_values(second_id)))
    trigger_id, foreign_id = trigger.id, foreign.id
    runs = AgentRunService(session)

    parent = track(
        await runs.create_agent_run(
            user_id=user_id,
            agent_id=agent_id,
            conversation_id=first_id,
            trigger_message_id=trigger_id,
            status="succeeded",
            risk_level="low",
            safety_status="passed",
            prompt_tokens=0,
            completion_tokens=0,
        )
    )
    child = track(
        await runs.create_agent_run(
            user_id=user_id,
            agent_id=agent_id,
            conversation_id=first_id,
            parent_run_id=parent.id,
            status="succeeded",
            risk_level="low",
            safety_status="passed",
            prompt_tokens=0,
            completion_tokens=0,
        )
    )
    assert child.parent_run_id == parent.id
    base = {
        "user_id": user_id,
        "agent_id": agent_id,
        "conversation_id": first_id,
        "status": "pending",
        "risk_level": "low",
        "safety_status": "pending",
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }
    with pytest.raises(NotFoundError):
        await runs.create_agent_run(**dict(base, agent_id=uuid4()))
    with pytest.raises(NotFoundError):
        await runs.create_agent_run(**dict(base, conversation_id=uuid4()))
    with pytest.raises(NotFoundError):
        await runs.create_agent_run(**dict(base, trigger_message_id=uuid4()))
    with pytest.raises(ValidationError):
        await runs.create_agent_run(**dict(base, trigger_message_id=foreign_id))
    with pytest.raises(NotFoundError):
        await runs.create_agent_run(**dict(base, parent_run_id=uuid4()))


@pytest.mark.asyncio
async def test_audit_log_service_rules_and_append_only(service_context: tuple) -> None:
    session, track = service_context
    user = track(await UserService(session).create_user(**user_values()))
    agent = track(await AgentService(session).create_agent(**agent_values()))
    conversation = track(
        await ConversationService(session).create_conversation(
            user_id=user.id, agent_id=agent.id, status="active", context={}
        )
    )
    run = track(
        await AgentRunService(session).create_agent_run(
            user_id=user.id,
            agent_id=agent.id,
            conversation_id=conversation.id,
            status="succeeded",
            risk_level="low",
            safety_status="passed",
            prompt_tokens=0,
            completion_tokens=0,
        )
    )
    user_id, run_id = user.id, run.id
    audits = AuditLogService(session)
    audit = track(
        await audits.create_audit_log(
            actor_user_id=user_id,
            agent_run_id=run_id,
            action="service.test",
            resource_type="agent_run",
            resource_id=run_id,
            risk_level="low",
            safety_status="passed",
            outcome="success",
            details={},
        )
    )
    assert await audits.get_audit_log(audit.id) is audit
    with pytest.raises(NotFoundError):
        await audits.create_audit_log(
            actor_user_id=uuid4(),
            action="invalid",
            resource_type="user",
            risk_level="low",
            outcome="failure",
            details={},
        )
    with pytest.raises(NotFoundError):
        await audits.create_audit_log(
            agent_run_id=uuid4(),
            action="invalid",
            resource_type="agent_run",
            risk_level="low",
            outcome="failure",
            details={},
        )
    assert not hasattr(audits, "update") and not hasattr(audits, "delete")
