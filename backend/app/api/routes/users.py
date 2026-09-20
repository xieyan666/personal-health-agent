"""User CRUD endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from backend.app.api.deps import get_user_service
from backend.app.schemas import UserCreate, UserResponse, UserUpdate
from backend.app.services import UserService


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await service.create_user(**payload.model_dump())


@router.get("", response_model=List[UserResponse])
async def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    service: UserService = Depends(get_user_service),
) -> List[UserResponse]:
    return await service.list_users(offset, limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await service.get_user(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await service.update_user(
        user_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    service: UserService = Depends(get_user_service),
) -> Response:
    await service.delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
