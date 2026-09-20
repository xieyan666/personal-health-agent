from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.auth.jwt import get_current_user
from backend.app.core.database import get_db
from backend.app.models import RiskAssessment
from backend.app.services.risk_assessment import assess_user
router=APIRouter(prefix='/health/risk',tags=['health-risk'])
@router.get('')
async def risk(current_user=Depends(get_current_user),session:AsyncSession=Depends(get_db)):
    await assess_user(session,current_user.id)
    rows=(await session.scalars(select(RiskAssessment).where(RiskAssessment.user_id==current_user.id).order_by(RiskAssessment.risk_type))).all()
    return [{'risk_type':x.risk_type,'level':x.level,'description':x.description,'recommendation':x.recommendation,'source':x.source} for x in rows]
