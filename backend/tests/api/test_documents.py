"""Real PostgreSQL and MinIO integration tests for Document ingestion."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Document, KnowledgeBase, User
from backend.app.services import DocumentIngestionService, KnowledgeBaseService
from backend.app.services.exceptions import NotFoundError, ValidationError
from backend.app.services.file_storage import FileStorageService
from backend.tests.api.test_conversations import user_payload


CONTENT = b"test document"


async def setup_knowledge_base(client: object, track_id: object) -> UUID:
    user = await client.post("/api/v1/users", json=user_payload())
    assert user.status_code == 201
    user_id = UUID(user.json()["id"])
    track_id(User, user_id)
    async with AsyncSessionFactory() as session:
        kb = await KnowledgeBaseService(session).create_knowledge_base(
            owner_user_id=user_id,
            name=f"test-kb-{uuid4().hex}",
            status="active",
            index_version=1,
            retrieval_config={},
        )
        kb_id = kb.id
    track_id(KnowledgeBase, kb_id)
    return kb_id


@pytest.mark.asyncio
async def test_document_upload_list_detail_download_and_delete(api_context: tuple) -> None:
    client, track_id = api_context
    kb_id = await setup_knowledge_base(client, track_id)
    document_ids: list[UUID] = []
    for filename in ("test.txt", "test.md", "test.pdf", "test.docx"):
        response = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": (filename, CONTENT, "application/octet-stream")},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "source_reference" not in body
        document_id = UUID(body["id"])
        document_ids.append(document_id)
        track_id(Document, document_id)
        assert body["size_bytes"] == len(CONTENT)
        assert body["status"] == "stored"

    listed = await client.get(f"/api/v1/knowledge-bases/{kb_id}/documents")
    assert listed.status_code == 200
    assert {UUID(item["id"]) for item in listed.json()} == set(document_ids)
    detail = await client.get(f"/api/v1/documents/{document_ids[0]}")
    assert detail.status_code == 200
    assert "source_reference" not in detail.json()
    downloaded = await client.get(f"/api/v1/documents/{document_ids[0]}/content")
    assert downloaded.status_code == 200
    assert downloaded.content == CONTENT
    assert downloaded.headers["content-type"].startswith("text/plain")
    assert "attachment" in downloaded.headers["content-disposition"]

    storage = FileStorageService()
    async with AsyncSessionFactory() as session:
        first_document = await session.get(Document, document_ids[0])
        assert first_document is not None
        first_key = first_document.source_reference["object_key"]
    deleted = await client.delete(f"/api/v1/documents/{document_ids[0]}")
    assert deleted.status_code == 204
    assert storage.object_exists(first_key) is False
    assert (await client.get(f"/api/v1/documents/{document_ids[0]}")).status_code == 404
    for document_id in document_ids[1:]:
        assert (await client.delete(f"/api/v1/documents/{document_id}")).status_code == 204


@pytest.mark.asyncio
async def test_document_validation_missing_resources_and_missing_object(api_context: tuple) -> None:
    client, track_id = api_context
    kb_id = await setup_knowledge_base(client, track_id)
    for filename in ("test.exe", "test.zip", "test.html"):
        response = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": (filename, CONTENT, "application/octet-stream")},
        )
        assert response.status_code == 422
    missing_kb = await client.post(
        f"/api/v1/knowledge-bases/{uuid4()}/documents",
        files={"file": ("test.txt", CONTENT, "text/plain")},
    )
    assert missing_kb.status_code == 404

    storage = FileStorageService()
    with pytest.raises(ValidationError):
        async with AsyncSessionFactory() as session:
            await DocumentIngestionService(session, storage).ingest_document(
                kb_id, "large.pdf", b"", storage.max_size_bytes + 1
            )

    upload = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("test.txt", CONTENT, "text/plain")},
    )
    document_id = UUID(upload.json()["id"])
    track_id(Document, document_id)
    assert "source_reference" not in upload.json()
    async with AsyncSessionFactory() as session:
        document = await session.get(Document, document_id)
        assert document is not None
        object_key = document.source_reference["object_key"]
    storage.delete_file(object_key)
    assert (await client.get(f"/api/v1/documents/{document_id}/content")).status_code == 404
    assert (await client.delete(f"/api/v1/documents/{document_id}")).status_code == 404
    assert (await client.get(f"/api/v1/documents/{document_id}")).status_code == 200
    for path in (
        f"/api/v1/documents/{uuid4()}",
        f"/api/v1/documents/{uuid4()}/content",
    ):
        assert (await client.get(path)).status_code == 404
    assert (await client.delete(f"/api/v1/documents/{uuid4()}")).status_code == 404


@pytest.mark.asyncio
async def test_database_failure_compensates_minio_object(api_context: tuple) -> None:
    client, track_id = api_context
    kb_id = await setup_knowledge_base(client, track_id)
    storage = FileStorageService()
    prefix = f"knowledge/{kb_id}/"
    assert list(storage.client.list_objects(storage.bucket, prefix=prefix, recursive=True)) == []
    async with AsyncSessionFactory() as session:
        with pytest.raises(Exception):
            await DocumentIngestionService(session, storage).ingest_document(
                kb_id,
                f"{'x' * 260}.txt",
                CONTENT,
                len(CONTENT),
            )
    assert list(storage.client.list_objects(storage.bucket, prefix=prefix, recursive=True)) == []
    async with AsyncSessionFactory() as session:
        assert await DocumentIngestionService(session, storage).list_documents(kb_id) == []
