"""Document upload, metadata, content, and delete endpoints."""

from typing import List
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from backend.app.api.deps import get_document_ingestion_service
from backend.app.schemas import DocumentResponse
from backend.app.services.document_ingestion import DocumentIngestionService


router = APIRouter(tags=["documents"])


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: UUID,
    file: UploadFile = File(...),
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> DocumentResponse:
    content = await file.read()
    return await service.ingest_document(
        knowledge_base_id,
        file.filename or "",
        content,
        len(content),
    )


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=List[DocumentResponse],
)
async def list_documents(
    knowledge_base_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> List[DocumentResponse]:
    return await service.list_documents(knowledge_base_id, offset, limit)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> DocumentResponse:
    return await service.get_document(document_id)


@router.get("/documents/{document_id}/content")
async def download_document(
    document_id: UUID,
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> Response:
    downloaded = await service.download_document(document_id)
    encoded_name = quote(downloaded.filename, safe="")
    return Response(
        content=downloaded.content,
        media_type=downloaded.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> Response:
    await service.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
