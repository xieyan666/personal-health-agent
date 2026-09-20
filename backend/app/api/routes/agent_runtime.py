from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import json
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.runtime import AgentRuntimeService
from backend.app.core.database import get_db
from backend.app.schemas.runtime import AgentRuntimeRequest, AgentRuntimeResponse

router = APIRouter(tags=["agent-runtime"])


@router.post("/agents/{agent_id}/run", response_model=AgentRuntimeResponse)
async def run_agent(agent_id: UUID, request: AgentRuntimeRequest, session: AsyncSession = Depends(get_db)):
    return await AgentRuntimeService(session).run(request.user_id, agent_id, request.conversation_id, request.content)


@router.post("/agents/{agent_id}/stream")
async def stream_agent(agent_id: UUID, request: AgentRuntimeRequest, session: AsyncSession = Depends(get_db)):
    async def events():
        async for item in AgentRuntimeService(session).stream_run(request.user_id, agent_id, request.conversation_id, request.content):
            event_type = item.pop("type")
            yield f"event: {event_type}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
