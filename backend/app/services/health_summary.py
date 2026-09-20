import json
from datetime import date, timedelta, timezone, datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.exceptions import ServiceError
from backend.app.models import HealthProfile, SleepRecord, ExerciseRecord, HeartRateRecord, HealthSummary
from backend.app.services.health_analysis_rules import analyze
from backend.app.services.llm_service import LLMService

def _as_list(value):
    """Keep the API contract stable even when an LLM returns a scalar value."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or value == "":
        return []
    return [str(value)]

def _normalize_summary(value):
    value = value if isinstance(value, dict) else {}
    return {
        "overall": str(value.get("overall") or ""),
        "findings": _as_list(value.get("findings")),
        "attention": _as_list(value.get("attention")),
        "suggestions": _as_list(value.get("suggestions")),
    }

async def build_summary(session: AsyncSession, user_id, force=False):
    if not force:
        cached=await session.scalar(select(HealthSummary).where(HealthSummary.user_id==user_id,HealthSummary.period=='30days',func.date(HealthSummary.created_at)==date.today()).order_by(HealthSummary.created_at.desc()))
        if cached:
            normalized = _normalize_summary(cached.summary_content)
            if normalized != cached.summary_content:
                cached.summary_content = normalized
                await session.commit()
            return normalized
    end=date.today(); start=end-timedelta(days=29)
    p=await session.scalar(select(HealthProfile).where(HealthProfile.user_id==user_id)); avg_sleep=await session.scalar(select(func.avg(SleepRecord.sleep_duration)).where(SleepRecord.user_id==user_id,SleepRecord.record_date>=start,SleepRecord.record_date<=end)); avg_ex=await session.scalar(select(func.avg(ExerciseRecord.exercise_duration)).where(ExerciseRecord.user_id==user_id,ExerciseRecord.record_date>=start,ExerciseRecord.record_date<=end)); avg_hr=await session.scalar(select(func.avg(HeartRateRecord.average_heart_rate)).where(HeartRateRecord.user_id==user_id,HeartRateRecord.record_date>=start,HeartRateRecord.record_date<=end)); bmi=round(float(p.weight)/((float(p.height)/100)**2),1) if p and p.height and p.weight else None
    profile={'age':p.age if p else None,'gender':p.gender if p else None,'bmi':bmi}; trend={'sleep':{'average':round(float(avg_sleep),1) if avg_sleep else None},'exercise':{'average_minutes':round(float(avg_ex),1) if avg_ex else None},'heart_rate':{'average':round(float(avg_hr),1) if avg_hr else None}}; rules=analyze(profile,trend)
    prompt=f'你是一名企业健康管理AI助手。只能根据数据生成JSON健康摘要，不进行医学诊断。用户信息:{profile} 健康趋势:{trend} 规则分析:{rules} 输出JSON字段 overall,findings,attention,suggestions。'
    try: raw=await LLMService().answer(prompt); content=json.loads(raw)
    except Exception as exc: raise ServiceError('健康摘要生成失败') from exc
    content = _normalize_summary(content)
    session.add(HealthSummary(user_id=user_id,period='30days',summary_content=content));await session.commit();return content
