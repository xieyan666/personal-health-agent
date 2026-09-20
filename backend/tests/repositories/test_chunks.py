"""Real PostgreSQL tests for DocumentChunkRepository."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Document, DocumentChunk, KnowledgeBase, User
from backend.app.repositories import DocumentChunkRepository


@pytest.mark.asyncio
async def test_chunk_repository_order_delete_and_no_commit(db_session) -> None:
    user_id = uuid4()
    user = User(
        id=user_id,
        username=f"repo_chunk_user_{uuid4().hex}",
        display_name="Chunk Repo User",
        auth_source="local",
        status="active",
        timezone="Asia/Shanghai",
    )
    kb = KnowledgeBase(
        owner_user_id=user_id,
        name=f"repo-chunk-kb-{uuid4().hex}",
        status="active",
        index_version=1,
        retrieval_config={},
    )
    first_doc = Document(
        knowledge_base=kb,
        name="first.txt",
        source_type="upload",
        source_reference={},
        status="stored",
        metadata_={},
    )
    second_doc = Document(
        knowledge_base=kb,
        name="second.txt",
        source_type="upload",
        source_reference={},
        status="stored",
        metadata_={},
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add_all([kb, first_doc, second_doc])
    await db_session.flush()
    repository = DocumentChunkRepository(db_session)
    first_chunks = [
        await repository.create(
            document_id=first_doc.id,
            chunk_index=index,
            content=f"chunk-{index}",
            char_count=len(f"chunk-{index}"),
        )
        for index in (2, 0, 1)
    ]
    second_chunk = await repository.create(
        document_id=second_doc.id,
        chunk_index=0,
        content="other",
        char_count=5,
    )
    assert [item.chunk_index for item in await repository.list_by_document_id(first_doc.id)] == [0, 1, 2]
    assert await repository.exists_by_document_and_index(first_doc.id, 1) is True
    assert await repository.exists_by_document_and_index(first_doc.id, 9) is False

    async with AsyncSessionFactory() as independent:
        assert await independent.scalar(
            select(DocumentChunk).where(DocumentChunk.id == first_chunks[0].id)
        ) is None

    assert await repository.delete_by_document_id(first_doc.id) == 3
    assert await repository.list_by_document_id(first_doc.id) == []
    assert await repository.get_by_id(second_chunk.id) is second_chunk
