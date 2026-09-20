"""Committed Service test sessions with precise UUID cleanup."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, AsyncIterator, Callable, DefaultDict, Set, Tuple, Type
from uuid import UUID

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionFactory, engine
from backend.app.models import (
    Agent,
    AgentRun,
    AuditLog,
    Conversation,
    Document,
    DocumentChunk,
    KnowledgeBase,
    Message,
    ModelConfig,
    ModelProvider,
    Tool,
    User,
)


Track = Callable[[Any], Any]


@pytest_asyncio.fixture
async def service_context() -> AsyncIterator[Tuple[AsyncSession, Track]]:
    tracked: DefaultDict[Type[Any], Set[UUID]] = defaultdict(set)

    def track(instance: Any) -> Any:
        tracked[type(instance)].add(instance.id)
        return instance

    async with AsyncSessionFactory() as session:
        try:
            yield session, track
        finally:
            await session.rollback()
            # Cascade cleanup for every tracked conversation, including rows
            # the test never explicitly track()ed (e.g. streamed replies or
            # failed agent runs).  Order matters:
            #   agent_runs.trigger_message_id -> messages
            #   messages.conversation_id       -> conversations
            tracked_conversations = tracked.get(Conversation)
            if tracked_conversations:
                # audit_logs.agent_run_id -> agent_runs (may be untracked)
                run_ids_for_conversations = select(AgentRun.id).where(
                    AgentRun.conversation_id.in_(tracked_conversations)
                )
                await session.execute(
                    delete(AuditLog).where(AuditLog.agent_run_id.in_(run_ids_for_conversations))
                )
                await session.execute(
                    delete(AgentRun).where(AgentRun.conversation_id.in_(tracked_conversations))
                )
                await session.execute(
                    delete(Message).where(Message.conversation_id.in_(tracked_conversations))
                )
            document_ids = tracked.get(Document)
            if document_ids:
                await session.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids))
                )
            cleanup_order = [
                AuditLog,
                AgentRun,
                Message,
                DocumentChunk,
                Conversation,
                Document,
                KnowledgeBase,
                Agent,
                ModelConfig,
                ModelProvider,
                Tool,
                User,
            ]
            for model in cleanup_order:
                identifiers = tracked.get(model)
                if identifiers:
                    await session.execute(
                        delete(model)
                        .where(model.id.in_(identifiers))
                        .execution_options(synchronize_session=False)
                    )
            await session.commit()
    await engine.dispose()
