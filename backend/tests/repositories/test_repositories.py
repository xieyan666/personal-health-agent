"""Real PostgreSQL tests for all P0 repositories."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import User
from backend.app.repositories import (
    AgentRepository,
    AgentRunRepository,
    AuditLogRepository,
    ConversationRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
    MessageRepository,
    ModelConfigRepository,
    ModelProviderRepository,
    ToolRepository,
    UserRepository,
)


def unique(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def user_values(**overrides: object) -> dict:
    values = {
        "username": unique("user"),
        "display_name": "Repository User",
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
        "name": "Repository Agent",
        "category": "daily_health",
        "status": "active",
        "config": {},
        "version": 1,
    }
    values.update(overrides)
    return values


async def create_user_agent(
    session: AsyncSession,
) -> tuple:
    user = await UserRepository(session).create(**user_values())
    agent = await AgentRepository(session).create(**agent_values())
    return user, agent


@pytest.mark.asyncio
async def test_base_and_user_repository_crud_pagination_no_commit(
    db_session: AsyncSession,
) -> None:
    repository = UserRepository(db_session)
    baseline_count = len(await repository.list(offset=0, limit=100))
    external_id = unique("employee")
    first = await repository.create(
        **user_values(
            auth_source="oidc",
            external_user_id=external_id,
            password_hash=None,
        )
    )
    second = await repository.create(**user_values())
    third = await repository.create(**user_values())

    assert await repository.get_by_id(first.id) is first
    assert await repository.get_by_username(first.username) is first
    assert await repository.get_by_email(first.email) is first
    assert await repository.get_by_external_identity("oidc", external_id) is first
    created_ids = {first.id, second.id, third.id}
    page_one = await repository.list(offset=baseline_count, limit=2)
    page_two = await repository.list(offset=baseline_count + 2, limit=2)
    assert {user.id for user in page_one + page_two} == created_ids
    assert len(page_one) == 2
    assert len(page_two) == 1
    with pytest.raises(ValueError):
        await repository.list(offset=-1, limit=1)
    with pytest.raises(ValueError):
        await repository.list(offset=0, limit=101)

    async with AsyncSessionFactory() as independent:
        visible = await independent.scalar(
            select(User).where(User.username == first.username)
        )
        assert visible is None

    assert await repository.update(first, display_name="Updated") is first
    assert first.display_name == "Updated"
    with pytest.raises(ValueError):
        await repository.update(first, id=uuid4())
    with pytest.raises(ValueError):
        await repository.update(first, _sa_instance_state=None)

    await repository.delete(second)
    assert await repository.get_by_id(second.id) is None
    assert third in await repository.list()


@pytest.mark.asyncio
async def test_agent_repository_scope_queries(db_session: AsyncSession) -> None:
    user = await UserRepository(db_session).create(**user_values())
    repository = AgentRepository(db_session)
    system = await repository.create(**agent_values(scope="system"))
    personal = await repository.create(
        **agent_values(scope="personal", owner_user_id=user.id)
    )

    assert await repository.get_by_code(system.code) is system
    assert await repository.list_by_owner_user_id(user.id) == [personal]
    assert system in await repository.list_system_agents()
    assert personal in await repository.list_personal_agents()


@pytest.mark.asyncio
async def test_model_provider_and_config_repositories(db_session: AsyncSession) -> None:
    providers = ModelProviderRepository(db_session)
    configs = ModelConfigRepository(db_session)
    provider = await providers.create(
        name=unique("provider"), provider_type="llm", status="active", config={}
    )
    config = await configs.create(
        provider_id=provider.id,
        name=unique("config"),
        model_name="test-model",
        model_type="chat",
        status="active",
        parameters={},
    )

    assert await providers.get_by_name(provider.name) is provider
    assert await configs.get_by_name(config.name) is config
    assert await configs.list_by_provider_id(provider.id) == [config]


@pytest.mark.asyncio
async def test_conversation_and_message_repositories_order_and_children(
    db_session: AsyncSession,
) -> None:
    user, agent = await create_user_agent(db_session)
    conversations = ConversationRepository(db_session)
    messages = MessageRepository(db_session)
    conversation = await conversations.create(
        user_id=user.id,
        agent_id=agent.id,
        title="Repository Conversation",
        status="active",
        context={},
    )
    now = datetime.now(timezone.utc)
    first = await messages.create(
        conversation_id=conversation.id,
        role="user",
        content="first",
        content_data={},
        status="completed",
        source_type="user",
        source_reference={},
        risk_level="low",
        safety_status="passed",
        created_at=now,
    )
    second = await messages.create(
        conversation_id=conversation.id,
        parent_message_id=first.id,
        role="assistant",
        content="second",
        content_data={},
        status="completed",
        source_type="model",
        source_reference={},
        risk_level="low",
        safety_status="passed",
        created_at=now + timedelta(seconds=1),
    )

    assert await conversations.get_by_id(conversation.id) is conversation
    assert await conversations.list_by_user_id(user.id) == [conversation]
    assert await conversations.list_by_agent_id(agent.id) == [conversation]
    assert await conversations.list_by_user_and_agent(user.id, agent.id) == [conversation]
    assert await messages.list_by_conversation_id(conversation.id) == [first, second]
    assert await messages.list_children(first.id) == [second]


@pytest.mark.asyncio
async def test_knowledge_document_and_tool_repositories(db_session: AsyncSession) -> None:
    user = await UserRepository(db_session).create(**user_values())
    knowledge_bases = KnowledgeBaseRepository(db_session)
    documents = DocumentRepository(db_session)
    tools = ToolRepository(db_session)
    kb = await knowledge_bases.create(
        owner_user_id=user.id,
        name="Repository KB",
        status="active",
        index_version=1,
        retrieval_config={},
    )
    document = await documents.create(
        knowledge_base_id=kb.id,
        name="test.txt",
        source_type="upload",
        source_reference={},
        status="ready",
        metadata_={},
    )
    implementation_ref = unique("builtin:health.bmi")
    tool = await tools.create(
        name=unique("tool"),
        display_name="BMI",
        tool_type="builtin",
        implementation_ref=implementation_ref,
        status="active",
        risk_level="low",
        requires_approval=False,
        input_schema={},
        config={},
    )

    assert await knowledge_bases.get_by_owner_and_name(user.id, "Repository KB") is kb
    assert await knowledge_bases.list_by_owner_user_id(user.id) == [kb]
    assert await documents.list_by_knowledge_base_id(kb.id) == [document]
    assert await tools.get_by_name(tool.name) is tool
    assert await tools.get_by_implementation_ref(implementation_ref) is tool


@pytest.mark.asyncio
async def test_agent_run_and_append_only_audit_repositories(
    db_session: AsyncSession,
) -> None:
    user, agent = await create_user_agent(db_session)
    conversation = await ConversationRepository(db_session).create(
        user_id=user.id,
        agent_id=agent.id,
        title="Run Conversation",
        status="active",
        context={},
    )
    runs = AgentRunRepository(db_session)
    parent = await runs.create(
        user_id=user.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        status="completed",
        risk_level="low",
        safety_status="passed",
        prompt_tokens=0,
        completion_tokens=0,
    )
    child = await runs.create(
        user_id=user.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        parent_run_id=parent.id,
        status="completed",
        risk_level="low",
        safety_status="passed",
        prompt_tokens=0,
        completion_tokens=0,
    )
    audits = AuditLogRepository(db_session)
    audit = await audits.create(
        actor_user_id=user.id,
        agent_run_id=parent.id,
        action="repository.test",
        resource_type="agent_run",
        resource_id=parent.id,
        risk_level="low",
        safety_status="passed",
        outcome="success",
        details={},
    )

    assert parent in await runs.list_by_agent_id(agent.id)
    assert parent in await runs.list_by_conversation_id(conversation.id)
    assert await runs.list_by_parent_run_id(parent.id) == [child]
    assert await audits.get_by_id(audit.id) is audit
    assert await audits.list_by_user_id(user.id) == [audit]
    assert await audits.list_by_agent_run_id(parent.id) == [audit]
    assert audit in await audits.list()
    assert not hasattr(audits, "update")
    assert not hasattr(audits, "delete")
