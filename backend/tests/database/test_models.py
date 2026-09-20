"""Integration tests for the P0 SQLAlchemy models on real PostgreSQL."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionFactory, engine
from backend.app.models import (
    Agent,
    AgentRun,
    AuditLog,
    Conversation,
    Document,
    KnowledgeBase,
    Message,
    ModelConfig,
    ModelProvider,
    Tool,
    User,
)


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def make_user(**overrides: object) -> User:
    values = {
        "username": unique_name("user"),
        "display_name": "Database Test User",
        "auth_source": "local",
        "password_hash": "test-hash-not-a-secret",
        "status": "active",
        "timezone": "Asia/Shanghai",
    }
    values.update(overrides)
    return User(**values)


def make_agent(**overrides: object) -> Agent:
    values = {
        "scope": "system",
        "owner_user_id": None,
        "code": unique_name("agent"),
        "name": "Database Test Agent",
        "category": "daily_health",
        "status": "active",
        "config": {},
        "version": 1,
    }
    values.update(overrides)
    return Agent(**values)


def make_conversation(user: User, agent: Agent) -> Conversation:
    return Conversation(
        user_id=user.id,
        agent_id=agent.id,
        title="Database test conversation",
        status="active",
        context={},
    )


def make_message(conversation: Conversation, role: str, content: str) -> Message:
    return Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        content_data={},
        status="completed",
        source_type="user" if role == "user" else "model",
        source_reference={"test": True},
        risk_level="low",
        safety_status="passed",
    )


async def flush_user_agent(session: AsyncSession) -> tuple[User, Agent]:
    user = make_user()
    agent = make_agent()
    session.add_all([user, agent])
    await session.flush()
    return user, agent


@pytest.mark.asyncio
async def test_user_crud_and_external_identity(db_session: AsyncSession) -> None:
    local = make_user()
    external = make_user(
        username=unique_name("oidc"),
        auth_source="oidc",
        external_user_id="employee-001",
        password_hash=None,
    )
    db_session.add_all([local, external])
    await db_session.commit()

    loaded = await db_session.scalar(select(User).where(User.id == local.id))
    assert loaded is local
    loaded.display_name = "Updated Test User"
    await db_session.commit()
    assert loaded.display_name == "Updated Test User"
    assert external.password_hash is None

    await db_session.delete(local)
    await db_session.commit()
    assert await db_session.get(User, local.id) is None


@pytest.mark.asyncio
async def test_username_unique_and_session_rollback(db_session: AsyncSession) -> None:
    username = unique_name("duplicate")
    first = make_user(username=username)
    second = make_user(username=username)
    db_session.add_all([first, second])
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    assert (
        await db_session.scalar(select(User).where(User.id.in_([first.id, second.id])))
    ) is None


@pytest.mark.asyncio
async def test_external_identity_unique(db_session: AsyncSession) -> None:
    identity = unique_name("employee")
    db_session.add_all(
        [
            make_user(auth_source="oidc", external_user_id=identity, password_hash=None),
            make_user(auth_source="oidc", external_user_id=identity, password_hash=None),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_agent_scope_owner_constraint_and_category(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    system = make_agent(category="medical_health")
    personal = make_agent(scope="personal", owner_user_id=user.id, category="daily_health")
    db_session.add_all([system, personal])
    await db_session.commit()
    assert system.owner_user_id is None
    assert personal.owner_user_id == user.id
    assert {system.category, personal.category} == {"medical_health", "daily_health"}

    db_session.add(make_agent(scope="personal", owner_user_id=None))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_model_provider_model_config_relationship(db_session: AsyncSession) -> None:
    provider = ModelProvider(
        name=unique_name("provider"), provider_type="llm", status="active", config={}
    )
    config = ModelConfig(
        provider=provider,
        name=unique_name("model_config"),
        model_name="test-model",
        model_type="chat",
        status="active",
        parameters={"temperature": 0},
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(provider, ["model_configs"])
    assert provider.model_configs == [config]


@pytest.mark.asyncio
async def test_conversation_messages_and_parent_reference(db_session: AsyncSession) -> None:
    user, agent = await flush_user_agent(db_session)
    conversation = make_conversation(user, agent)
    db_session.add(conversation)
    await db_session.flush()
    first = make_message(conversation, "user", "first")
    second = make_message(conversation, "assistant", "second")
    second.parent = first
    db_session.add_all([first, second])
    await db_session.commit()
    await db_session.refresh(conversation, ["messages"])
    await db_session.refresh(second, ["parent"])
    assert conversation.messages == [first, second]
    assert second.parent is first
    assert second.source_reference == {"test": True}
    assert second.risk_level == "low" and second.safety_status == "passed"


@pytest.mark.asyncio
async def test_knowledge_base_document_relationship_and_unique(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    kb = KnowledgeBase(
        owner_user_id=user.id,
        name="Employee Handbook",
        status="active",
        vector_collection="kb-test",
        index_version=1,
        retrieval_config={},
    )
    document = Document(
        knowledge_base=kb,
        name="health.md",
        source_type="upload",
        source_reference={},
        status="ready",
        metadata_={},
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(kb, ["documents"])
    assert kb.documents == [document]
    assert kb.vector_collection == "kb-test" and kb.index_version == 1
    assert not hasattr(Document, "owner_user_id")
    assert not hasattr(Document, "vector_collection")

    db_session.add(
        KnowledgeBase(
            owner_user_id=user.id,
            name="Employee Handbook",
            status="active",
            index_version=1,
            retrieval_config={},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_tool_required_implementation_reference(db_session: AsyncSession) -> None:
    tool = Tool(
        name=unique_name("bmi_calculator"),
        display_name="BMI Calculator",
        tool_type="builtin",
        implementation_ref="builtin:health.bmi",
        status="active",
        risk_level="low",
        requires_approval=False,
        input_schema={},
        config={},
    )
    db_session.add(tool)
    await db_session.commit()
    assert await db_session.get(Tool, tool.id) is tool

    db_session.add(
        Tool(
            name=unique_name("invalid_tool"),
            display_name="Invalid",
            tool_type="builtin",
            implementation_ref=None,
            status="active",
            risk_level="low",
            requires_approval=False,
            input_schema={},
            config={},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_agent_run_message_and_parent_relationships(db_session: AsyncSession) -> None:
    user, agent = await flush_user_agent(db_session)
    conversation = make_conversation(user, agent)
    db_session.add(conversation)
    await db_session.flush()
    trigger = make_message(conversation, "user", "trigger")
    output = make_message(conversation, "assistant", "output")
    db_session.add_all([trigger, output])
    await db_session.flush()
    parent = AgentRun(
        user_id=user.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        trigger_message_id=trigger.id,
        output_message_id=output.id,
        status="completed",
        input_summary="input summary",
        output_summary="output summary",
        risk_level="low",
        safety_status="passed",
        prompt_tokens=1,
        completion_tokens=1,
    )
    child = AgentRun(
        user_id=user.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        parent_run=parent,
        status="completed",
        risk_level="low",
        safety_status="passed",
        prompt_tokens=0,
        completion_tokens=0,
    )
    db_session.add_all([parent, child])
    await db_session.commit()
    await db_session.refresh(parent, ["trigger_message", "output_message", "child_runs"])
    await db_session.refresh(child, ["parent_run"])
    assert parent.trigger_message is trigger and parent.output_message is output
    assert child.parent_run is parent and child in parent.child_runs
    assert parent.input_summary == "input summary"
    assert parent.output_summary == "output summary"
    assert not hasattr(AgentRun, "input") and not hasattr(AgentRun, "output")


@pytest.mark.asyncio
async def test_audit_log_save_and_no_orm_cascade(db_session: AsyncSession) -> None:
    user, agent = await flush_user_agent(db_session)
    run = AgentRun(
        user_id=user.id,
        agent_id=agent.id,
        status="completed",
        risk_level="low",
        safety_status="passed",
        prompt_tokens=0,
        completion_tokens=0,
    )
    audit = AuditLog(
        actor_user_id=user.id,
        agent_run=run,
        action="agent_run.completed",
        resource_type="agent_run",
        risk_level="low",
        safety_status="passed",
        outcome="success",
        details={"test": True},
    )
    db_session.add(audit)
    await db_session.commit()
    assert audit.created_at is not None
    assert not hasattr(AuditLog, "updated_at")
    audit_id = audit.id

    await db_session.delete(run)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    assert await db_session.get(AuditLog, audit_id) is not None


@pytest.mark.asyncio
async def test_timestamp_mixin_updates() -> None:
    user = make_user()
    async with AsyncSessionFactory() as session:
        try:
            session.add(user)
            await session.commit()
            created_at = user.created_at
            updated_at = user.updated_at
            assert created_at is not None and updated_at is not None

            await asyncio.sleep(0.02)
            user.display_name = "Timestamp Updated"
            await session.commit()
            await session.refresh(user)
            assert user.created_at == created_at
            assert user.updated_at > updated_at
        finally:
            await session.delete(user)
            await session.commit()
    await engine.dispose()
