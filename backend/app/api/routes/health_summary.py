from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.services.health_summary import build_summary
router=APIRouter(prefix='/health-summary',tags=['health-summary'])
@router.get('/{user_id}')
async def summary(user_id: UUID,current_user=Depends(get_current_user),session:AsyncSession=Depends(get_db)):
    if user_id != current_user.id: raise HTTPException(403,'无权访问其他用户健康摘要')
    try:return await build_summary(session,user_id)
    except Exception as exc: raise HTTPException(503,'健康摘要暂时不可用') from exc
