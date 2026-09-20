"""Admin orchestration for the existing MinIO -> Chunk -> Embedding -> Qdrant RAG path."""
from __future__ import annotations

from uuid import UUID, uuid4
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Agent, Document, DocumentChunk, KnowledgeBase, ModelConfig
from backend.app.services.chunk import ChunkService
from backend.app.services.document_ingestion import DocumentIngestionService
from backend.app.services.exceptions import ConflictError, NotFoundError, ValidationError
from backend.app.services.file_storage import FileStorageService
from backend.app.services.knowledge_document_parser import KnowledgeDocumentParser
from backend.app.services.qdrant_index import QdrantIndexService
from backend.app.services.retrieval import RetrievalService


class KnowledgeWorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion = DocumentIngestionService(session)
        self.chunker = ChunkService(session)
        self.indexer = QdrantIndexService(session)
        self.retrieval = RetrievalService(session)
        self.storage = FileStorageService()
        self.parser = KnowledgeDocumentParser()

    async def _embedding_config(self) -> ModelConfig:
        config = await self.session.scalar(select(ModelConfig).where(ModelConfig.model_type == "embedding", ModelConfig.status == "active").order_by(ModelConfig.created_at.asc()))
        if config is None:
            raise ValidationError("No active embedding model configuration is available")
        return config

    async def create_base(self, owner_id: UUID, *, name: str, domain: str, description: str | None, enabled: bool, agent_ids: list[UUID]) -> KnowledgeBase:
        if await self.session.scalar(select(KnowledgeBase).where(KnowledgeBase.owner_user_id == owner_id, KnowledgeBase.name == name)):
            raise ConflictError("Knowledge base name already exists")
        embedding = await self._embedding_config()
        kb = KnowledgeBase(id=uuid4(), owner_user_id=owner_id, name=name, description=description, status="active" if enabled else "disabled", embedding_model_config_id=embedding.id, vector_collection=f"knowledge_{uuid4().hex}", retrieval_config={"domain": domain, "top_k": 5})
        self.session.add(kb)
        await self.session.flush()
        await self.bind_agents(kb, agent_ids, commit=False)
        await self.session.commit()
        await self.session.refresh(kb)
        return kb

    async def bind_agents(self, kb: KnowledgeBase, agent_ids: list[UUID], *, commit: bool = True) -> None:
        agents = list((await self.session.scalars(select(Agent).where(Agent.id.in_(agent_ids)))).all()) if agent_ids else []
        if len(agents) != len(set(agent_ids)):
            raise NotFoundError("One or more selected agents do not exist")
        selected = {str(agent.id) for agent in agents}
        all_agents = list((await self.session.scalars(select(Agent))).all())
        for agent in all_agents:
            cfg = dict(agent.config or {})
            ids = [str(item) for item in cfg.get("knowledge_base_ids", []) if str(item) != str(kb.id)]
            if str(agent.id) in selected:
                ids.append(str(kb.id))
            cfg["knowledge_base_ids"] = ids
            # Runtime compatibility: its existing RAG path reads `rag`; the
            # primary selected base remains explicit and never comes from UI text.
            if str(agent.id) in selected:
                cfg["rag"] = {"enabled": True, "knowledge_base_id": str(kb.id), "embedding_model_config_id": str(kb.embedding_model_config_id), "top_k": 5}
            elif isinstance(cfg.get("rag"), dict) and cfg["rag"].get("knowledge_base_id") == str(kb.id):
                cfg["rag"] = {"enabled": False}
            agent.config = cfg
        if commit:
            await self.session.commit()

    async def process_upload(self, kb: KnowledgeBase, filename: str, data: bytes) -> Document:
        document = await self.ingestion.ingest_document(kb.id, filename, data, len(data))
        document.status = "processing"
        document.error_message = None
        await self.session.commit()
        try:
            parsed = await self.parser.parse(filename, data)
            if len(parsed.text.strip()) < 20:
                raise ValidationError("Document parser did not extract enough readable text")
            chunks = await self.chunker.create_chunks(document.id, parsed.text)
            if not chunks:
                raise ValidationError("Document did not produce any searchable chunks")
            if kb.embedding_model_config_id is None:
                raise ValidationError("Knowledge base has no embedding configuration")
            indexed = await self.indexer.index_document(document.id, kb.embedding_model_config_id)
            document.status = "indexed"
            document.metadata_ = {"parser": parsed.parser, "pages": parsed.pages, "char_count": len(parsed.text), "chunk_count": len(chunks), "indexed_count": indexed.indexed_count}
            await self.session.commit()
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)[:500]
            await self.session.commit()
        await self.session.refresh(document)
        return document

    async def retry_document(self, kb: KnowledgeBase, document: Document) -> Document:
        key = document.source_reference.get("object_key")
        if not isinstance(key, str):
            raise NotFoundError("Document source is unavailable")
        if await self._has_chunks(document.id):
            # Remove both vector points and persisted chunks before producing a
            # fresh index; retry must never leave duplicate chunks behind.
            await self.indexer.delete_document_index(document.id)
            await self.chunker.delete_chunks(document.id)
        data = self.storage.get_file(key)
        return await self.process_existing(kb, document, data)

    async def process_existing(self, kb: KnowledgeBase, document: Document, data: bytes) -> Document:
        document.status = "processing"; document.error_message = None; await self.session.commit()
        try:
            parsed = await self.parser.parse(document.name, data)
            if len(parsed.text.strip()) < 20: raise ValidationError("Document parser did not extract enough readable text")
            chunks = await self.chunker.create_chunks(document.id, parsed.text)
            if kb.embedding_model_config_id is None: raise ValidationError("Knowledge base has no embedding configuration")
            indexed = await self.indexer.index_document(document.id, kb.embedding_model_config_id)
            document.status = "indexed"; document.metadata_ = {"parser": parsed.parser, "pages": parsed.pages, "char_count": len(parsed.text), "chunk_count": len(chunks), "indexed_count": indexed.indexed_count}
        except Exception as exc:
            document.status = "failed"; document.error_message = str(exc)[:500]
        await self.session.commit(); await self.session.refresh(document); return document

    async def _has_chunks(self, document_id: UUID) -> bool:
        return bool(await self.session.scalar(select(DocumentChunk.id).where(DocumentChunk.document_id == document_id).limit(1)))

    async def delete_document(self, kb: KnowledgeBase, document: Document) -> None:
        """Delete a document and every resource created by its ingestion.

        The order is intentional: remove vector points, chunk rows, original
        MinIO object, then the document metadata row.
        """
        if document.knowledge_base_id != kb.id:
            raise NotFoundError("Document does not belong to this knowledge base")
        if await self._has_chunks(document.id):
            await self.indexer.delete_document_index(document.id)
        await self.chunker.delete_chunks(document.id)
        object_key = (document.source_reference or {}).get("object_key")
        if isinstance(object_key, str):
            try:
                self.storage.delete_file(object_key)
            except NotFoundError:
                pass
        await self.session.delete(document)
        await self.session.commit()

    async def delete_base(self, kb: KnowledgeBase) -> None:
        """Delete only an empty, unbound knowledge base.

        Documents must be deliberately removed first; this prevents accidental
        loss of the original MinIO source files through a single UI click.
        """
        if await self.session.scalar(select(Document.id).where(Document.knowledge_base_id == kb.id).limit(1)):
            raise ConflictError("请先删除知识库中的全部文档")
        for agent in (await self.session.scalars(select(Agent))).all():
            if str(kb.id) not in [str(item) for item in (agent.config or {}).get("knowledge_base_ids", [])]:
                continue
            cfg = dict(agent.config or {})
            cfg["knowledge_base_ids"] = [str(item) for item in cfg.get("knowledge_base_ids", []) if str(item) != str(kb.id)]
            if isinstance(cfg.get("rag"), dict) and cfg["rag"].get("knowledge_base_id") == str(kb.id):
                cfg["rag"] = {"enabled": False}
            agent.config = cfg
        await self.session.delete(kb)
        await self.session.commit()

    async def summary(self, kb: KnowledgeBase) -> dict:
        docs = int((await self.session.scalar(select(func.count(Document.id)).where(Document.knowledge_base_id == kb.id))) or 0)
        chunks = int((await self.session.scalar(select(func.count(DocumentChunk.id)).join(Document).where(Document.knowledge_base_id == kb.id))) or 0)
        agents = []
        for agent in (await self.session.scalars(select(Agent))).all():
            if str(kb.id) in [str(v) for v in (agent.config or {}).get("knowledge_base_ids", [])]:
                agents.append({"id": str(agent.id), "name": agent.name, "code": agent.code})
        return {"id": kb.id, "name": kb.name, "domain": (kb.retrieval_config or {}).get("domain", "通用健康知识"), "description": kb.description, "status": kb.status, "document_count": docs, "chunk_count": chunks, "vector_progress": 100 if docs and chunks else 0, "updated_at": kb.updated_at.isoformat(), "agents": agents}
