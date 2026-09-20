"""Model configuration CRUD endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from backend.app.api.deps import get_model_config_service
from backend.app.auth.jwt import require_role
from backend.app.schemas import ModelConfigCreate, ModelConfigResponse, ModelConfigUpdate
from backend.app.services import ModelConfigService


router = APIRouter(prefix="/model-configs", tags=["model-configs"])
admin = require_role("admin", "company_admin", "system_admin")


@router.post("", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_model_config(
    payload: ModelConfigCreate,
    _: None = Depends(admin),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigResponse:
    return await service.create_model_config(**payload.model_dump())


@router.get("", response_model=List[ModelConfigResponse])
async def list_model_configs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    provider_id: Optional[UUID] = Query(default=None),
    _: None = Depends(admin),
    service: ModelConfigService = Depends(get_model_config_service),
) -> List[ModelConfigResponse]:
    return await service.list_model_configs(offset, limit, provider_id)


@router.get("/{config_id}", response_model=ModelConfigResponse)
async def get_model_config(
    config_id: UUID,
    _: None = Depends(admin),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigResponse:
    return await service.get_model_config(config_id)


@router.patch("/{config_id}", response_model=ModelConfigResponse)
async def update_model_config(
    config_id: UUID,
    payload: ModelConfigUpdate,
    _: None = Depends(admin),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigResponse:
    return await service.update_model_config(
        config_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_config(
    config_id: UUID,
    _: None = Depends(admin),
    service: ModelConfigService = Depends(get_model_config_service),
) -> Response:
    await service.delete_model_config(config_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
