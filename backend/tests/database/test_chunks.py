"""Real PostgreSQL tests for DocumentChunk model constraints and relationship."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.models import Document, DocumentChunk, KnowledgeBase, User


def user_values() -> dict:
    return {
        "username": f"chunk_user_{uuid4().hex}",
        "display_name": "Chunk User",
        "auth_source": "local",
        "status": "active",
        "timezone": "Asia/Shanghai",
    }


@pytest.mark.asyncio
async def test_document_chunk_constraints_and_relationship(db_session) -> None:
    user_id = uuid4()
    user = User(id=user_id, **user_values())
    db_session.add(user)
    await db_session.flush()
    kb = KnowledgeBase(
        owner_user_id=user_id,
        name=f"chunk-kb-{uuid4().hex}",
        status="active",
        index_version=1,
        retrieval_config={},
    )
    document_id = uuid4()
    document = Document(
        id=document_id,
        knowledge_base=kb,
        name="chunk.txt",
        source_type="upload",
        source_reference={},
        status="stored",
        metadata_={},
    )
    chunk_id = uuid4()
    chunk = DocumentChunk(
        id=chunk_id, document=document, chunk_index=0, content="hello", char_count=5
    )
    db_session.add_all([kb, document, chunk])
    await db_session.commit()
    await db_session.refresh(document, ["chunks"])
    assert document.chunks == [chunk]
    assert chunk.document_id == document_id
    assert chunk.char_count == len(chunk.content)

    duplicate = DocumentChunk(
        document_id=document_id, chunk_index=0, content="again", char_count=5
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    for values in (
        {"document_id": document_id, "chunk_index": -1, "content": "x", "char_count": 1},
        {"document_id": document_id, "chunk_index": 1, "content": "x", "char_count": -1},
        {"document_id": uuid4(), "chunk_index": 1, "content": "x", "char_count": 1},
    ):
        db_session.add(DocumentChunk(**values))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
