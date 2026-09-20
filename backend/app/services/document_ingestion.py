"""Coordinate Document metadata and MinIO object lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Document
from backend.app.repositories import DocumentChunkRepository, DocumentRepository, KnowledgeBaseRepository
from backend.app.services.exceptions import ConflictError, NotFoundError
from backend.app.services.file_storage import FileStorageService


@dataclass(frozen=True)
class DownloadedDocument:
    content: bytes
    filename: str
    content_type: str


class DocumentIngestionService:
    STORED_STATUS = "stored"
    UPLOAD_SOURCE_TYPE = "upload"

    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorageService | None = None,
    ) -> None:
        self.session = session
        self.documents = DocumentRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)
        self.storage = storage if storage is not None else FileStorageService()

    async def ingest_document(
        self,
        knowledge_base_id: UUID,
        original_filename: str,
        data: bytes,
        size: int,
    ) -> Document:
        if await self.knowledge_bases.get_by_id(knowledge_base_id) is None:
            raise NotFoundError(f"Knowledge base not found: {knowledge_base_id}")

        document_id = uuid4()
        stored = self.storage.upload_file(
            knowledge_base_id,
            document_id,
            original_filename,
            data,
            size,
        )
        try:
            document = await self.documents.create(
                id=document_id,
                knowledge_base_id=knowledge_base_id,
                name=original_filename,
                source_type=self.UPLOAD_SOURCE_TYPE,
                source_reference={
                    "bucket": stored.bucket,
                    "object_key": stored.object_key,
                },
                mime_type=stored.content_type,
                size_bytes=stored.size,
                status=self.STORED_STATUS,
                metadata_={},
            )
            await self.session.commit()
            await self.session.refresh(document)
            return document
        except Exception:
            await self.session.rollback()
            try:
                self.storage.delete_file(stored.object_key)
            except Exception:
                pass
            raise

    async def list_documents(
        self, knowledge_base_id: UUID, offset: int = 0, limit: int = 100
    ) -> List[Document]:
        if await self.knowledge_bases.get_by_id(knowledge_base_id) is None:
            raise NotFoundError(f"Knowledge base not found: {knowledge_base_id}")
        return await self.documents.list_by_knowledge_base_id(
            knowledge_base_id, offset, limit
        )

    async def get_document(self, document_id: UUID) -> Document:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        return document

    async def download_document(self, document_id: UUID) -> DownloadedDocument:
        document = await self.get_document(document_id)
        if await self.chunks.exists_by_document_id(document_id):
            raise ConflictError(f"Document has chunks and cannot be deleted: {document_id}")
        object_key = self._object_key(document)
        return DownloadedDocument(
            content=self.storage.get_file(object_key),
            filename=document.name,
            content_type=document.mime_type or "application/octet-stream",
        )

    async def delete_document(self, document_id: UUID) -> None:
        document = await self.get_document(document_id)
        object_key = self._object_key(document)
        self.storage.delete_file(object_key)
        try:
            await self.documents.delete(document)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _object_key(document: Document) -> str:
        object_key = document.source_reference.get("object_key")
        if not isinstance(object_key, str):
            raise NotFoundError(f"Document object locator missing: {document.id}")
        return object_key
