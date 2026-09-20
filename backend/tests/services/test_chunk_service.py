from uuid import uuid4

import pytest

from backend.app.models import Document, KnowledgeBase, User
from backend.app.services.chunk import ChunkService
from backend.app.services.exceptions import ConflictError, NotFoundError
from backend.app.services.text_chunker import split_text


def test_split_text_rules():
    assert split_text("") == []
    assert split_text("   ") == []
    chunks = split_text("a" * 2200)
    assert [len(c) for c in chunks] == [1000, 1000, 600]
    assert chunks[0][-200:] == chunks[1][:200]


@pytest.mark.asyncio
async def test_chunk_service_create_list_delete(service_context):
    session, track = service_context
    user = track(User(id=uuid4(), username=f"chunk-{uuid4().hex}", email=f"chunk-{uuid4()}@example.com", display_name="Chunk", auth_source="local"))
    session.add(user)
    await session.flush()
    kb = track(KnowledgeBase(id=uuid4(), owner_user_id=user.id, name="chunks", status="active"))
    session.add(kb)
    document = track(Document(id=uuid4(), knowledge_base_id=kb.id, name="x.txt", source_type="upload", source_reference={}, status="stored"))
    session.add(document)
    await session.commit()
    service = ChunkService(session)
    result = await service.create_chunks(document.id, "a" * 1800)
    assert [c.chunk_index for c in result] == [0, 1]
    assert result[-1].char_count == 1000
    with pytest.raises(ConflictError):
        await service.create_chunks(document.id, "again")
    assert await service.delete_chunks(document.id) == 2
    assert await service.list_chunks(document.id) == []


@pytest.mark.asyncio
async def test_chunk_service_missing_document(service_context):
    session, _ = service_context
    with pytest.raises(NotFoundError):
        await ChunkService(session).create_chunks(uuid4(), "text")
