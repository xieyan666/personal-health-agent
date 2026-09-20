"""Agent CRUD endpoints."""

from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_agent_service
from backend.app.schemas import AgentCreate, AgentResponse, AgentUpdate
from backend.app.services import AgentService


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    return await service.create_agent(**payload.model_dump())


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    scope: Optional[Literal["system", "personal"]] = Query(default=None),
    owner_user_id: Optional[UUID] = Query(default=None),
    service: AgentService = Depends(get_agent_service),
) -> List[AgentResponse]:
    if scope is not None and owner_user_id is not None:
        raise HTTPException(
            status_code=422,
            detail="scope and owner_user_id cannot be combined",
        )
    return await service.list_agents(offset, limit, scope, owner_user_id)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    return await service.get_agent(agent_id)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    return await service.update_agent(
        agent_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    service: AgentService = Depends(get_agent_service),
) -> Response:
    await service.delete_agent(agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
