"""Knowledge metadata business operations."""

from __future__ import annotations

from typing import Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Document, KnowledgeBase
from backend.app.repositories import DocumentRepository, KnowledgeBaseRepository, UserRepository
from backend.app.services.base import BaseService
from backend.app.services.exceptions import ConflictError, NotFoundError


class KnowledgeBaseService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = KnowledgeBaseRepository(session)
        self.users = UserRepository(session)

    async def get_knowledge_base(self, knowledge_base_id: UUID) -> KnowledgeBase:
        item = await self.repository.get_by_id(knowledge_base_id)
        if item is None:
            raise NotFoundError(f"Knowledge base not found: {knowledge_base_id}")
        return item

    async def list_knowledge_bases(self, owner_user_id: UUID, offset: int = 0, limit: int = 100) -> List[KnowledgeBase]:
        return await self.repository.list_by_owner_user_id(owner_user_id, offset, limit)

    async def create_knowledge_base(self, **values: Any) -> KnowledgeBase:
        async with self._transaction():
            owner_id = values["owner_user_id"]
            if await self.users.get_by_id(owner_id) is None:
                raise NotFoundError(f"Owner user not found: {owner_id}")
            if await self.repository.get_by_owner_and_name(owner_id, values["name"]):
                raise ConflictError("Knowledge base name already exists for owner")
            return await self.repository.create(**values)

    async def update_knowledge_base(self, knowledge_base_id: UUID, **values: Any) -> KnowledgeBase:
        async with self._transaction():
            item = await self.get_knowledge_base(knowledge_base_id)
            return await self.repository.update(item, **values)

    async def delete_knowledge_base(self, knowledge_base_id: UUID) -> None:
        async with self._transaction():
            await self.repository.delete(await self.get_knowledge_base(knowledge_base_id))


class DocumentService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repository = DocumentRepository(session)
        self.knowledge_bases = KnowledgeBaseRepository(session)

    async def get_document(self, document_id: UUID) -> Document:
        document = await self.repository.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        return document

    async def list_documents(self, knowledge_base_id: UUID, offset: int = 0, limit: int = 100) -> List[Document]:
        return await self.repository.list_by_knowledge_base_id(knowledge_base_id, offset, limit)

    async def create_document(self, **values: Any) -> Document:
        async with self._transaction():
            kb_id = values["knowledge_base_id"]
            if await self.knowledge_bases.get_by_id(kb_id) is None:
                raise NotFoundError(f"Knowledge base not found: {kb_id}")
            return await self.repository.create(**values)

    async def update_document(self, document_id: UUID, **values: Any) -> Document:
        async with self._transaction():
            document = await self.get_document(document_id)
            return await self.repository.update(document, **values)

    async def delete_document(self, document_id: UUID) -> None:
        async with self._transaction():
            await self.repository.delete(await self.get_document(document_id))
