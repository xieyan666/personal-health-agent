"""Model provider CRUD endpoints (admin roles only)."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from backend.app.api.deps import get_model_provider_service
from backend.app.auth.jwt import require_role
from backend.app.schemas import (
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderUpdate,
)
from backend.app.services import ModelProviderService


router = APIRouter(prefix="/model-providers", tags=["model-providers"])
admin = require_role("admin", "company_admin", "system_admin")


@router.post("", response_model=ModelProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ModelProviderCreate,
    _: None = Depends(admin),
    service: ModelProviderService = Depends(get_model_provider_service),
) -> ModelProviderResponse:
    return await service.create_provider(**payload.model_dump())


@router.get("", response_model=List[ModelProviderResponse])
async def list_providers(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    _: None = Depends(admin),
    service: ModelProviderService = Depends(get_model_provider_service),
) -> List[ModelProviderResponse]:
    return await service.list_providers(offset, limit)


@router.get("/{provider_id}", response_model=ModelProviderResponse)
async def get_provider(
    provider_id: UUID,
    _: None = Depends(admin),
    service: ModelProviderService = Depends(get_model_provider_service),
) -> ModelProviderResponse:
    return await service.get_provider(provider_id)


@router.patch("/{provider_id}", response_model=ModelProviderResponse)
async def update_provider(
    provider_id: UUID,
    payload: ModelProviderUpdate,
    _: None = Depends(admin),
    service: ModelProviderService = Depends(get_model_provider_service),
) -> ModelProviderResponse:
    return await service.update_provider(
        provider_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    _: None = Depends(admin),
    service: ModelProviderService = Depends(get_model_provider_service),
) -> Response:
    await service.delete_provider(provider_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
