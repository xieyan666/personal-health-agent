from datetime import datetime, timezone
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models import SleepRecord, ExerciseRecord, HeartRateRecord, RiskAssessment, HealthCheckIndicator, HealthCheckReport
async def assess_user(session: AsyncSession, user_id):
    sleep=float(await session.scalar(select(func.avg(SleepRecord.sleep_duration)).where(SleepRecord.user_id==user_id)) or 0)
    exercise=float(await session.scalar(select(func.avg(ExerciseRecord.exercise_duration)).where(ExerciseRecord.user_id==user_id)) or 0)
    hr=float(await session.scalar(select(func.avg(HeartRateRecord.resting_heart_rate)).where(HeartRateRecord.user_id==user_id)) or 0)
    items=[]
    level='high' if sleep and sleep<6 else 'medium' if sleep and sleep<7 else 'low'; items.append(('sleep',level,f'近30天平均睡眠 {sleep:.1f} 小时' if sleep else '暂无睡眠数据','保持固定作息，睡前减少电子设备使用。'))
    level='medium' if exercise and exercise*7<150 else 'low'; items.append(('exercise',level,f'近期平均每日运动 {exercise:.1f} 分钟' if exercise else '暂无运动数据','逐步增加每周运动时间，目标每周至少150分钟。'))
    level='medium' if hr>90 else 'low'; items.append(('heart_rate',level,f'平均静息心率 {hr:.0f} bpm' if hr else '暂无心率数据','保持规律运动并持续关注心率变化。'))
    # Structured report abnormalities are deterministic inputs to the risk engine.
    latest_report = await session.scalar(select(HealthCheckReport).where(HealthCheckReport.user_id == user_id).order_by(HealthCheckReport.report_date.desc()).limit(1))
    if latest_report is not None:
        abnormal = list((await session.scalars(select(HealthCheckIndicator).where(HealthCheckIndicator.report_id == latest_report.id, HealthCheckIndicator.flag.in_(("high", "low"))))).all())
        if abnormal:
            names = '、'.join(item.item_name for item in abnormal[:3])
            items.append(('report', 'medium', f'最新体检报告存在需要关注指标：{names}', '请结合体检报告中的参考范围调整生活方式，必要时咨询专业医疗人员。'))
    await session.execute(delete(RiskAssessment).where(RiskAssessment.user_id==user_id))
    now=datetime.now(timezone.utc)
    for typ,lvl,desc,reco in items: session.add(RiskAssessment(user_id=user_id,risk_type=typ,level=lvl,description=desc,recommendation=reco,source='Wearable',assessed_at=now))
    await session.commit(); return items
