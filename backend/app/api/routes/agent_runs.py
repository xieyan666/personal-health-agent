"""AgentRun CRUD endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_agent_run_service
from backend.app.schemas import AgentRunCreate, AgentRunResponse, AgentRunUpdate
from backend.app.services import AgentRunService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.post("", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_run(
    payload: AgentRunCreate,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunResponse:
    return await service.create_agent_run(**payload.model_dump())


@router.get("", response_model=List[AgentRunResponse])
async def list_agent_runs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    agent_id: Optional[UUID] = Query(default=None),
    conversation_id: Optional[UUID] = Query(default=None),
    parent_run_id: Optional[UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    service: AgentRunService = Depends(get_agent_run_service),
) -> List[AgentRunResponse]:
    if sum(value is not None for value in (agent_id, conversation_id, parent_run_id)) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_id, conversation_id and parent_run_id are mutually exclusive",
        )
    return await service.list_agent_runs(
        offset=offset,
        limit=limit,
        agent_id=agent_id,
        conversation_id=conversation_id,
        parent_run_id=parent_run_id,
        status=status_filter,
    )


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: UUID,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunResponse:
    return await service.get_agent_run(run_id)


@router.patch("/{run_id}", response_model=AgentRunResponse)
async def update_agent_run(
    run_id: UUID,
    payload: AgentRunUpdate,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunResponse:
    return await service.update_agent_run(
        run_id, **payload.model_dump(exclude_unset=True)
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_run(
    run_id: UUID,
    service: AgentRunService = Depends(get_agent_run_service),
) -> Response:
    await service.delete_agent_run(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
