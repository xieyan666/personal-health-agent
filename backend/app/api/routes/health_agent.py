from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.exceptions import ServiceError
from backend.app.models import Agent, Conversation, Message
from backend.app.schemas.health_agent import HealthChatRequest, HealthChatResponse
from backend.app.services.llm_service import LLMService
from backend.app.tools.health_profile import get_authorized_health_profile_context
from backend.app.services.data_authorization_service import DataAccessNotAuthorized
from backend.app.agent.health_supervisor.mental_health.context import build_mental_assessment_prompt
from backend.app.agent.runtime import AgentRuntimeService

router = APIRouter(prefix="/health-agent", tags=["health-agent"])


async def _build_prompt(payload: HealthChatRequest, *, current_user, session: AsyncSession) -> tuple[str | None, str | None]:
    """Route explicit assessment-result consultations through Mental Health Agent.

    Ordinary health questions retain the existing Health Supervisor + profile
    tool path.  The opaque source context is persisted only as metadata and is
    never rendered as a questionnaire answer.
    """
    if payload.source_context is not None:
        return await build_mental_assessment_prompt(
            session,
            user_id=current_user.id,
            assessment_id=payload.source_context.assessment_id,
            declared_type=payload.source_context.assessment_type,
            user_message=payload.message,
        )
    try:
        context = await get_authorized_health_profile_context(
            session,
            current_user.id,
            agent_id="health_supervisor_agent",
            purpose="用于 AI 健康助手个性化建议",
        )
        return f"当前员工健康数据（仅供分析，不要泄露内部字段）：{json.dumps(context, ensure_ascii=False)}\n用户问题：{payload.message}", None
    except DataAccessNotAuthorized:
        return f"用户问题：{payload.message}\n用户尚未授权读取个人健康档案，请提供不依赖个人健康数据的通用健康建议。", None


def _message_context(payload: HealthChatRequest) -> dict:
    if payload.source_context is None:
        return {}
    return {"source_context": payload.source_context.model_dump(mode="json")}


@router.post("/chat", response_model=HealthChatResponse)
async def chat(payload: HealthChatRequest, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> HealthChatResponse:
    if payload.conversation_id is not None:
        conversation = await session.scalar(select(Conversation).where(Conversation.id == payload.conversation_id))
        if conversation is None:
            raise HTTPException(404, "会话不存在")
        if conversation.user_id != current_user.id:
            raise HTTPException(403, "无权访问其他用户会话")
    else:
        agent = await session.scalar(select(Agent).where(Agent.scope == "system", Agent.status == "active", Agent.code == "health_supervisor").limit(1))
        if agent is None:
            agent = await session.scalar(select(Agent).where(Agent.scope == "system", Agent.status == "active").order_by(Agent.created_at.asc()).limit(1))
        if agent is None:
            raise HTTPException(503, "健康助手尚未配置")
        conversation = Conversation(user_id=current_user.id, agent_id=agent.id, title=payload.message[:80], status="active", context={})
        session.add(conversation)
        await session.flush()
    # The generic path is executed by the persisted AgentRuntime.  This creates
    # the real root AgentRun and, when configured, child runs for specialist
    # agents.  The assessment-context path remains on its dedicated safety flow.
    if payload.source_context is None:
        try:
            result = await AgentRuntimeService(session).run(current_user.id, conversation.agent_id, conversation.id, payload.message)
            return HealthChatResponse(answer=result.content, conversation_id=conversation.id)
        except ServiceError as exc:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试") from exc
        except Exception:
            await session.rollback()
            raise
    session.add(Message(conversation_id=conversation.id, role="user", content=payload.message, status="succeeded", risk_level="low", safety_status="safe", content_data=_message_context(payload), source_reference={}))
    await session.flush()
    try:
        prompt, direct_answer = await _build_prompt(payload, current_user=current_user, session=session)
        answer = direct_answer or await LLMService().answer(prompt or "")
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail="未找到本次心理测评结果") from exc
    except ServiceError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试") from exc
    session.add(Message(conversation_id=conversation.id, role="assistant", content=answer, status="succeeded", risk_level="low", safety_status="safe", content_data={}, source_reference={}))
    conversation.last_message_at = datetime.now(timezone.utc)
    await session.commit()
    return HealthChatResponse(answer=answer, conversation_id=conversation.id)


@router.post("/chat/stream")
async def chat_stream(payload: HealthChatRequest, current_user=Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    async def events():
        conversation = None
        try:
            if payload.conversation_id is not None:
                conversation = await session.scalar(select(Conversation).where(Conversation.id == payload.conversation_id))
                if conversation is None or conversation.user_id != current_user.id:
                    yield "event: error\ndata: {\"detail\":\"会话不存在或无权访问\"}\n\n"
                    return
            else:
                agent = await session.scalar(select(Agent).where(Agent.scope == "system", Agent.status == "active", Agent.code == "health_supervisor").limit(1))
                if agent is None:
                    agent = await session.scalar(select(Agent).where(Agent.scope == "system", Agent.status == "active").order_by(Agent.created_at.asc()).limit(1))
                if agent is None:
                    yield "event: error\ndata: {\"detail\":\"健康助手尚未配置\"}\n\n"
                    return
                conversation = Conversation(user_id=current_user.id, agent_id=agent.id, title=payload.message[:80], status="active", context={})
                session.add(conversation)
                await session.flush()
            if payload.source_context is None:
                async for event in AgentRuntimeService(session).stream_run(current_user.id, conversation.agent_id, conversation.id, payload.message):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                return
            session.add(Message(conversation_id=conversation.id, role="user", content=payload.message, status="succeeded", risk_level="low", safety_status="safe", content_data=_message_context(payload), source_reference={}))
            await session.flush()
            pieces: list[str] = []
            prompt, direct_answer = await _build_prompt(payload, current_user=current_user, session=session)
            if direct_answer is not None:
                pieces.append(direct_answer)
                yield f"data: {json.dumps({'content': direct_answer, 'conversation_id': str(conversation.id)}, ensure_ascii=False)}\n\n"
            else:
                async for piece in LLMService().stream_answer(prompt or ""):
                    pieces.append(piece)
                    yield f"data: {json.dumps({'content': piece, 'conversation_id': str(conversation.id)}, ensure_ascii=False)}\n\n"
            answer = "".join(pieces)
            if not answer.strip():
                raise ServiceError("DeepSeek returned an empty answer")
            session.add(Message(conversation_id=conversation.id, role="assistant", content=answer, status="succeeded", risk_level="low", safety_status="safe", content_data={}, source_reference={}))
            conversation.last_message_at = datetime.now(timezone.utc)
            await session.commit()
            yield "event: done\ndata: {}\n\n"
        except LookupError:
            await session.rollback()
            yield "event: error\ndata: {\"detail\":\"未找到本次心理测评结果\"}\n\n"
        except ServiceError:
            await session.rollback()
            yield "event: error\ndata: {\"detail\":\"AI 服务暂时不可用，请稍后重试\"}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
