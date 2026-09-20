"""Seed development test data for the health services page.

Catalog, activities, an example booking and annual benefits for employee001.
Idempotent; re-running skips existing rows.

    docker exec -e PYTHONPATH=/app life-health-agent-api sh -c \
      "cd /app/backend && python3 -m scripts.seed_health_services"
"""

import asyncio
from datetime import date, timedelta

from sqlalchemy import select
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import EmployeeHealthBenefit, HealthActivity, HealthActivityParticipant, HealthService, HealthServiceBooking, User

SERVICES = [
    # (category, name, description, duration, mode, suitability, is_annual_check, sort)
    ("medical_exam", "年度健康体检", "覆盖基础指标、生化、影像与肿瘤标志物的年度全面检查。", 120, "offline", "所有员工年度例行健康检查", True, 1),
    ("medical_exam", "专项检查", "按年龄与风险因素定制的专项检查（心脑血管、甲状腺、胃肠镜等）。", 90, "offline", "有家族史或风险提示的员工", False, 2),
    ("medical_exam", "复查预约", "针对异常指标安排复查时间，跟踪指标变化。", 30, "offline", "体检发现异常指标需复查的员工", False, 3),
    ("medical_exam", "入职体检", "新员工入职体检，含基础检查与常见职业病筛查。", 60, "offline", "新入职员工", False, 4),
    ("medical_consult", "体检结果咨询", "体检发现异常指标后进行专业解读与咨询。", 30, "online", "体检发现异常指标、需要进一步了解的员工", False, 1),
    ("medical_consult", "全科健康咨询", "日常健康问题的全科医生线上咨询。", 20, "online", "有日常健康疑问的员工", False, 2),
    ("medical_consult", "营养相关医学咨询", "围绕慢性病、体重管理的营养医学建议。", 30, "online", "血脂/血糖/体重异常的员工", False, 3),
    ("medical_consult", "慢病健康管理咨询", "高血压、糖尿病等慢性病的长期健康管理指导。", 40, "online", "已有慢病诊断或高风险员工", False, 4),
    ("nutrition", "营养评估", "基于饮食记录与体测数据的营养状况评估。", 30, "online", "希望了解自身营养状况的员工", False, 1),
    ("nutrition", "个性化饮食指导", "结合健康档案与目标的个性化饮食方案。", 45, "online", "有减脂/增肌/控糖目标的员工", False, 2),
    ("nutrition", "减脂饮食方案", "科学减脂的饮食计划与执行辅导。", 45, "online", "超重或希望减脂的员工", False, 3),
    ("nutrition", "健康食谱", "符合均衡营养的每周健康食谱推荐。", 20, "online", "希望改善日常饮食结构的员工", False, 4),
    ("exercise", "运动能力评估", "评估心肺、力量与柔韧性，给出运动起点建议。", 40, "offline", "准备开始规律运动的员工", False, 1),
    ("exercise", "健身指导", "一对一/小组健身动作与计划指导。", 45, "offline", "有健身目标的员工", False, 2),
    ("exercise", "办公室肩颈训练", "针对久坐人群的肩颈放松与强化训练。", 20, "offline", "久坐办公、肩颈不适的员工", False, 3),
    ("exercise", "企业健走计划", "基于步数目标的团队健走支持与指导。", 30, "online", "参加企业健走活动的员工", False, 4),
    ("course", "睡眠健康讲座", "讲解睡眠节律、环境与习惯改善方法。", 60, "online", "有睡眠困扰的员工", False, 1),
    ("course", "饮食营养课程", "系统学习日常均衡饮食与常见误区。", 60, "online", "希望提升营养认知的员工", False, 2),
    ("course", "科学减脂课程", "从饮食与运动角度学习科学减脂。", 60, "online", "有减脂需求的员工", False, 3),
    ("course", "急救培训", "心肺复苏、AED 使用等基础急救技能培训。", 120, "offline", "所有员工（建议必修）", False, 4),
]

ACTIVITIES = [
    ("企业健走30天挑战", "walking", "每日步数挑战，坚持 30 天养成运动习惯。", date.today() - timedelta(days=6), date.today() + timedelta(days=24), "每日", None, 500, 326),
    ("办公室肩颈放松", "stretching", "每周三午间 20 分钟肩颈放松跟练。", None, None, "每周三 12:30", 20, 40, 22),
    ("健康饮食打卡活动", "diet", "连续 21 天健康饮食记录打卡。", date.today(), date.today() + timedelta(days=21), "每日", 10, 300, 0),
    ("科学减脂训练营", "exercise", "四周科学减脂训练营，含饮食与运动指导。", date.today() + timedelta(days=7), date.today() + timedelta(days=35), "每周一/三/五 18:00", 45, 60, 12),
]

BOOKINGS = [
    # (service_name, days_from_today, time, status, provider)
    ("营养评估", 4, "14:30", "confirmed", "营养师 李慧"),
    ("运动能力评估", -7, "10:00", "completed", "运动指导师 王强"),
]

BENEFITS = [
    ("annual_check", "年度体检", 1, 0),
    ("nutrition_consult", "营养咨询", 2, 0),
    ("sport_evaluation", "运动评估", 2, 1),
    ("medical_consult", "医疗健康咨询", 6, 2),
]


async def main() -> None:
    async with AsyncSessionFactory() as session:
        user = await session.scalar(select(User).where(User.username == "employee001"))
        if user is None:
            print("employee001 not found; skip")
            return

        existing = await session.scalar(select(HealthService).limit(1))
        if existing is None:
            for category, name, description, duration, mode, suitability, annual, sort in SERVICES:
                session.add(HealthService(
                    name=name, category=category, description=description,
                    duration_minutes=duration, delivery_mode=mode, suitability=suitability,
                    is_annual_check=annual, status="active", sort_order=sort,
                ))
            await session.flush()
            print("Seeded health services catalog")

        existing_activity = await session.scalar(select(HealthActivity).limit(1))
        if existing_activity is None:
            for name, activity_type, description, start, end, schedule, duration, capacity, participants in ACTIVITIES:
                session.add(HealthActivity(
                    name=name, activity_type=activity_type, description=description,
                    start_date=start, end_date=end, schedule=schedule,
                    duration_minutes=duration, capacity=capacity, participants=participants, status="active",
                ))
            await session.flush()
            print("Seeded health activities")

        existing_booking = await session.scalar(select(HealthServiceBooking).where(HealthServiceBooking.user_id == user.id).limit(1))
        if existing_booking is None:
            services = {item.name: item for item in (await session.scalars(select(HealthService))).all()}
            for name, days, time, status, provider in BOOKINGS:
                service = services.get(name)
                if service is None:
                    continue
                session.add(HealthServiceBooking(
                    user_id=user.id, service_id=service.id,
                    booking_date=date.today() + timedelta(days=days),
                    booking_time=time, status=status, provider=provider,
                ))
            await session.flush()
            print("Seeded example bookings")

        existing_benefit = await session.scalar(select(EmployeeHealthBenefit).where(EmployeeHealthBenefit.user_id == user.id).limit(1))
        if existing_benefit is None:
            for benefit_type, name, quota, used in BENEFITS:
                session.add(EmployeeHealthBenefit(
                    user_id=user.id, benefit_type=benefit_type, benefit_name=name,
                    annual_quota=quota, used_quota=used,
                ))
            await session.flush()
            print("Seeded employee health benefits")

        await session.commit()
        print("Seed complete")


if __name__ == "__main__":
    asyncio.run(main())
