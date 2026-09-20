"""JWT-protected administrator workspace for the existing RAG knowledge bases."""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db
from backend.app.auth.jwt import require_role
from backend.app.models import Agent, Document, KnowledgeBase, User
from backend.app.schemas.knowledge_workspace import KnowledgeBaseAgentsUpdate, KnowledgeBaseCreate, RetrievalTestRequest
from backend.app.services.exceptions import ConflictError, NotFoundError, ServiceError, ValidationError
from backend.app.services.knowledge_workspace import KnowledgeWorkspaceService

router = APIRouter(prefix="/admin/knowledge-bases", tags=["admin-knowledge"])
admin = require_role("admin", "company_admin", "system_admin")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError): return HTTPException(404, str(exc))
    if isinstance(exc, (ValidationError, ConflictError)): return HTTPException(422 if isinstance(exc, ValidationError) else 409, str(exc))
    if isinstance(exc, ServiceError): return HTTPException(503, "知识库基础服务暂不可用")
    return HTTPException(500, "知识库操作失败")


async def _owned(session: AsyncSession, kb_id: UUID, current: User) -> KnowledgeBase:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or (current.role != "system_admin" and kb.owner_user_id != current.id):
        raise HTTPException(404, "知识库不存在")
    return kb


@router.get("")
async def list_bases(session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.updated_at.desc())
    if current.role != "system_admin": stmt = stmt.where(KnowledgeBase.owner_user_id == current.id)
    service = KnowledgeWorkspaceService(session)
    return [await service.summary(kb) for kb in (await session.scalars(stmt)).all()]


@router.post("", status_code=201)
async def create_base(payload: KnowledgeBaseCreate, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    try:
        kb = await KnowledgeWorkspaceService(session).create_base(current.id, name=payload.name.strip(), domain=payload.domain.strip(), description=payload.description, enabled=payload.enabled, agent_ids=payload.agent_ids)
        return await KnowledgeWorkspaceService(session).summary(kb)
    except Exception as exc: raise _http(exc)


@router.get("/agents")
async def list_agents(session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    agents = (await session.scalars(select(Agent).where(Agent.status == "active").order_by(Agent.name))).all()
    return [{"id": str(agent.id), "name": agent.name, "code": agent.code, "category": agent.category} for agent in agents]


@router.get("/rag-status")
async def rag_status(session: AsyncSession = Depends(get_db), _: User = Depends(admin)):
    """RAG pipeline health + cross-base processing stats (no technical logs)."""
    from backend.app.models import DocumentChunk, ModelConfig
    from backend.app.core.qdrant import get_qdrant_client
    from backend.app.services.exceptions import ServiceError

    def probe_parser() -> str:
        for module in ("pypdf", "docling"):
            try:
                __import__(module)
                return "ok"
            except Exception:
                continue
        return "degraded"

    parser_status = probe_parser()
    try:
        from backend.app.services.text_chunker import split_text
        chunk_status = "ok" if callable(split_text) else "degraded"
    except Exception:
        chunk_status = "degraded"
    embedding_ok = bool(
        await session.scalar(select(ModelConfig.id).where(ModelConfig.model_type == "embedding", ModelConfig.status == "active").limit(1))
    )
    try:
        client = get_qdrant_client()
        await client.get_collections()
        qdrant_status = "ok"
    except Exception:
        qdrant_status = "degraded"

    docs = list((await session.scalars(select(Document).order_by(Document.updated_at.desc()))).all())
    pending = sum(1 for doc in docs if doc.status in ("stored", "processing"))
    failed = sum(1 for doc in docs if doc.status == "failed")
    indexed_rows = [doc for doc in docs if doc.status == "indexed"]
    last_indexed = indexed_rows[0].updated_at.isoformat() if indexed_rows else None
    chunk_total = int((await session.scalar(select(func.count(DocumentChunk.id)))) or 0)
    recent = [
        {
            "id": str(doc.id), "document_name": doc.name, "status": doc.status,
            "chunk_count": (doc.metadata_ or {}).get("chunk_count", 0),
            "updated_at": doc.updated_at.isoformat(), "error_message": doc.error_message,
        }
        for doc in docs[:6]
    ]
    return {
        "components": {
            "parser": {"name": "Document Parser", "status": parser_status},
            "chunker": {"name": "Chunk Service", "status": chunk_status},
            "embedding": {"name": "Embedding Model", "status": "ok" if embedding_ok else "degraded"},
            "qdrant": {"name": "Qdrant", "status": qdrant_status},
        },
        "stats": {
            "pending_documents": pending,
            "index_failures": failed,
            "total_chunks": chunk_total,
            "last_indexed_at": last_indexed,
        },
        "recent": recent,
    }


@router.get("/{kb_id}")
async def get_base(kb_id: UUID, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    return await KnowledgeWorkspaceService(session).summary(await _owned(session, kb_id, current))


@router.put("/{kb_id}/agents")
async def update_agents(kb_id: UUID, payload: KnowledgeBaseAgentsUpdate, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    kb = await _owned(session, kb_id, current)
    try:
        await KnowledgeWorkspaceService(session).bind_agents(kb, payload.agent_ids)
        return await KnowledgeWorkspaceService(session).summary(kb)
    except Exception as exc: raise _http(exc)


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: UUID, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    await _owned(session, kb_id, current)
    docs = (await session.scalars(select(Document).where(Document.knowledge_base_id == kb_id).order_by(Document.created_at.desc()))).all()
    return [{"id": str(doc.id), "name": doc.name, "status": doc.status, "size_bytes": doc.size_bytes, "mime_type": doc.mime_type, "error_message": doc.error_message, "metadata": doc.metadata_, "created_at": doc.created_at.isoformat(), "updated_at": doc.updated_at.isoformat()} for doc in docs]


@router.post("/{kb_id}/documents", status_code=201)
async def upload_document(kb_id: UUID, file: UploadFile = File(...), session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    kb = await _owned(session, kb_id, current)
    if not file.filename: raise HTTPException(422, "请选择需要上传的文件")
    data = await file.read()
    try:
        doc = await KnowledgeWorkspaceService(session).process_upload(kb, file.filename, data)
        return {"id": str(doc.id), "name": doc.name, "status": doc.status, "error_message": doc.error_message, "metadata": doc.metadata_}
    except Exception as exc: raise _http(exc)


@router.post("/{kb_id}/documents/{document_id}/retry")
async def retry_document(kb_id: UUID, document_id: UUID, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    kb = await _owned(session, kb_id, current)
    doc = await session.get(Document, document_id)
    if doc is None or doc.knowledge_base_id != kb.id: raise HTTPException(404, "文档不存在")
    try:
        result = await KnowledgeWorkspaceService(session).retry_document(kb, doc)
        return {"id": str(result.id), "name": result.name, "status": result.status, "error_message": result.error_message, "metadata": result.metadata_}
    except Exception as exc: raise _http(exc)


@router.delete("/{kb_id}/documents/{document_id}", status_code=204)
async def delete_document(kb_id: UUID, document_id: UUID, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    kb = await _owned(session, kb_id, current)
    doc = await session.get(Document, document_id)
    if doc is None or doc.knowledge_base_id != kb.id: raise HTTPException(404, "文档不存在")
    try:
        await KnowledgeWorkspaceService(session).delete_document(kb, doc)
    except Exception as exc: raise _http(exc)


@router.delete("/{kb_id}", status_code=204)
async def delete_base(kb_id: UUID, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    kb = await _owned(session, kb_id, current)
    try:
        await KnowledgeWorkspaceService(session).delete_base(kb)
    except Exception as exc: raise _http(exc)


@router.get("/{kb_id}/chunks")
async def list_chunks(kb_id: UUID, limit: int = 100, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    await _owned(session, kb_id, current)
    from backend.app.models import DocumentChunk
    rows = (await session.execute(select(DocumentChunk, Document).join(Document).where(Document.knowledge_base_id == kb_id).order_by(Document.created_at.desc(), DocumentChunk.chunk_index).limit(min(limit, 200)))).all()
    return [{"id": str(chunk.id), "document_id": str(doc.id), "document_name": doc.name, "chunk_index": chunk.chunk_index, "char_count": chunk.char_count, "content": chunk.content} for chunk, doc in rows]


@router.post("/{kb_id}/retrieve")
async def retrieve(kb_id: UUID, payload: RetrievalTestRequest, session: AsyncSession = Depends(get_db), current: User = Depends(admin)):
    kb = await _owned(session, kb_id, current)
    if kb.embedding_model_config_id is None: raise HTTPException(422, "知识库未配置 Embedding 模型")
    try:
        results = await KnowledgeWorkspaceService(session).retrieval.retrieve(kb.id, payload.query, kb.embedding_model_config_id, payload.top_k)
        documents = {doc.id: doc.name for doc in (await session.scalars(select(Document).where(Document.id.in_([item.document_id for item in results])))).all()}
        return {"items": [{"score": round(item.score, 4), "content": item.content, "document_id": str(item.document_id), "document_name": documents.get(item.document_id, "未知文档"), "chunk_index": item.chunk_index, "source": "Qdrant"} for item in results]}
    except Exception as exc: raise _http(exc)
