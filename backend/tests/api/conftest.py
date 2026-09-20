"""ASGI client and precise committed-data cleanup for API tests."""

from __future__ import annotations

from collections import defaultdict
from typing import AsyncIterator, Callable, DefaultDict, Set, Tuple, Type
from uuid import UUID

import httpx
import pytest_asyncio
from sqlalchemy import delete

from backend.app.core.database import AsyncSessionFactory, engine
from backend.app.main import app
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
    User,
)


TrackId = Callable[[Type[object], UUID], None]


@pytest_asyncio.fixture
async def api_context() -> AsyncIterator[Tuple[httpx.AsyncClient, TrackId]]:
    tracked: DefaultDict[Type[object], Set[UUID]] = defaultdict(set)

    def track_id(model: Type[object], object_id: UUID) -> None:
        tracked[model].add(object_id)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        try:
            yield client, track_id
        finally:
            async with AsyncSessionFactory() as session:
                document_ids = tracked.get(Document)
                if document_ids:
                    await session.execute(
                        delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids))
                    )
                for model in (
                    AuditLog,
                    DocumentChunk,
                    AgentRun,
                    Document,
                    Message,
                    Conversation,
                    KnowledgeBase,
                    Agent,
                    ModelConfig,
                    ModelProvider,
                    User,
                ):
                    identifiers = tracked.get(model)
                    if identifiers:
                        await session.execute(
                            delete(model)
                            .where(model.id.in_(identifiers))
                            .execution_options(synchronize_session=False)
                        )
                await session.commit()
    await engine.dispose()
