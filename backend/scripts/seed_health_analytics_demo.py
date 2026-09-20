"""Seed a deterministic, real database demo dataset for the admin
"员工健康分析" dashboard.

Generates 80 synthetic employees (analytics-demo-001..080) plus their health
profiles, weekly risk scores, risk assessments, exam reports & indicators,
health plans & tasks and mental checkins.  Everything is written into the
EXISTING tables (no new tables, no frontend mocks); the dashboard keeps
aggregating through the real API.

Idempotent: any existing ``analytics-demo-%`` rows are removed first, so the
script can be re-run safely without duplicating employees.

Run manually:
    cd backend && python -m scripts.seed_health_analytics_demo
"""

from __future__ import annotations

import asyncio
import random
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from backend.app.auth.security import hash_password
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import (
    Department,
    Employee,
    HealthCheckIndicator,
    HealthCheckReport,
    HealthPlan,
    HealthPlanTask,
    HealthProfile,
    HealthRiskScore,
    MentalCheckin,
    RiskAssessment,
    User,
)

RNG = random.Random(20260831)

DEPARTMENT_PLAN = [
    ("AI研发部", 10),
    ("产品部", 10),
    ("人力资源部", 8),
    ("人工智能部", 10),
    ("基础设施部", 8),
    ("市场销售部", 10),
    ("技术研发部", 10),
    ("数据平台部", 7),
    ("测试质量部", 7),
]

# per-department risk distribution: {department: [(risk_type, count), ...]}
DEPARTMENT_RISKS = {
    "AI研发部": [("sleep", 4), ("exercise", 2), ("abnormal", 2), ("stress", 1), ("heart_rate", 3)],
    "产品部": [("exercise", 4), ("sleep", 3), ("abnormal", 2), ("stress", 2), ("heart_rate", 1)],
    "人力资源部": [("sleep", 2), ("exercise", 1), ("abnormal", 2), ("stress", 1)],
    "人工智能部": [("sleep", 4), ("exercise", 3), ("abnormal", 2), ("stress", 1), ("heart_rate", 1)],
    "基础设施部": [("exercise", 4), ("sleep", 2), ("abnormal", 1), ("heart_rate", 2)],
    "市场销售部": [("stress", 5), ("sleep", 2), ("abnormal", 2), ("heart_rate", 2)],
    "技术研发部": [("sleep", 5), ("exercise", 2), ("abnormal", 2), ("stress", 2)],
    "数据平台部": [("exercise", 4), ("sleep", 2), ("abnormal", 1), ("stress", 1)],
    "测试质量部": [("sleep", 1), ("exercise", 1), ("abnormal", 2)],
}

RISK_META = {
    "sleep": ("睡眠不足", "夜间睡眠时长不足，影响恢复", "建议固定作息时间，保证7小时睡眠"),
    "exercise": ("运动不足", "每周中高强度运动时间低于推荐量", "建议每周累计150分钟中等强度运动"),
    "abnormal": ("体检指标异常", "体检存在超出参考范围的指标", "建议按体检建议复查异常指标"),
    "stress": ("心理压力偏高", "近期工作生活压力水平偏高", "建议劳逸结合，必要时联系EAP"),
    "heart_rate": ("心率异常趋势", "静息心率呈上升趋势", "建议避免熬夜与过量咖啡因"),
}
RISK_LEVELS = ["low", "medium", "high"]

# Exam items: (category, code, item_name, unit, ref_min, ref_max)
EXAM_ITEMS = [
    ("血脂", "uric_acid", "尿酸", "umol/L", 202.0, 416.0),
    ("血脂", "ldl_c", "LDL-C", "mmol/L", None, 3.36),
    ("血糖", "fasting_glucose", "空腹血糖", "mmol/L", 3.9, 6.1),
    ("肝功能", "alt", "ALT", "U/L", 7.0, 40.0),
    ("肝功能", "ast", "AST", "U/L", 13.0, 35.0),
    ("血脂", "total_cholesterol", "总胆固醇", "mmol/L", 3.0, 5.7),
    ("血脂", "triglyceride", "甘油三酯", "mmol/L", None, 1.7),
]

PLAN_TYPES = [
    ("睡眠改善", "sleep", "保证每日7小时睡眠"),
    ("运动改善", "exercise", "每周3次30分钟有氧运动"),
    ("饮食改善", "diet", "每日五蔬果，控制油盐糖"),
    ("压力恢复", "stress", "每日10分钟正念呼吸练习"),
]


async def cleanup_demo_data(session) -> int:
    """Remove previous demo users + their related rows. Returns removed count."""
    demo_user_ids = list(
        (
            await session.scalars(
                select(User.id).where(User.username.like("analytics-demo-%"))
            )
        ).all()
    )
    if not demo_user_ids:
        return 0
    for model in (HealthPlanTask, HealthPlan, MentalCheckin, RiskAssessment, HealthRiskScore, HealthCheckReport, HealthProfile, Employee):
        await session.execute(
            delete(model).where(model.user_id.in_(demo_user_ids))
        )
    await session.execute(delete(User).where(User.id.in_(demo_user_ids)))
    await session.commit()
    return len(demo_user_ids)


async def main() -> None:
    async with AsyncSessionFactory() as session:
        removed = await cleanup_demo_data(session)

        company = await session.scalar(select(Employee.company_id).limit(1))
        from backend.app.models import Company
        company_row = await session.scalar(select(Company).where(Company.code == "local-company"))
        if company_row is None:
            company_row = Company(name="演示企业", code="local-company")
            session.add(company_row)
            await session.flush()
        company_id = company_row.id

        # Ensure the "AI研发部" department exists so the RBAC department list
        # (used by the dashboard filter) contains it.
        existing_departments = set((await session.scalars(select(Department.name))).all())
        for department_name, _ in DEPARTMENT_PLAN:
            if department_name not in existing_departments:
                session.add(Department(name=department_name))
        await session.flush()

        password_hash = hash_password("demo123456")
        today = date.today()

        users: list[User] = []
        employees: list[Employee] = []
        index = 1
        for department_name, count in DEPARTMENT_PLAN:
            for _ in range(count):
                username = f"analytics-demo-{index:03d}"
                user = User(
                    username=username,
                    display_name=f"演示员工{index:03d}",
                    auth_source="local",
                    password_hash=password_hash,
                    role="employee",
                    status="active",
                    company_id=str(company_id),
                    department=department_name,
                )
                session.add(user)
                await session.flush()
                session.add(
                    Employee(
                        user_id=user.id,
                        company_id=company_id,
                        employee_no=f"DEMO{index:03d}",
                        name=f"演示员工{index:03d}",
                        department=department_name,
                        position=RNG.choice(["工程师", "专员", "经理", "设计师", "运营"]),
                        join_date=today - timedelta(days=RNG.randint(120, 900)),
                    )
                )
                users.append(user)
                index += 1
        await session.flush()
        user_ids = [user.id for user in users]
        print(f"created {len(users)} demo users (removed {removed} stale)")

        # ------------------------------------------------------------------
        # Health profiles: 72 of 80; 产品部 keeps 9/10 covered
        # ------------------------------------------------------------------
        profile_user_ids = list(user_ids[:72])
        profile_user_ids.remove(user_ids[19])   # 产品部第10人保持无数据
        profile_user_ids.append(user_ids[73])   # 测试质量部第1人补齐覆盖
        for user_id in profile_user_ids:
            session.add(
                HealthProfile(
                    user_id=user_id,
                    age=RNG.randint(23, 55),
                    gender=RNG.choice(["男", "女"]),
                    height=RNG.uniform(155, 188),
                    weight=RNG.uniform(48, 92),
                )
            )
        await session.flush()
        print(f"health_profiles: {len(profile_user_ids)}")

        # ------------------------------------------------------------------
        # Weekly health risk scores (5 stages: -28d .. today), 72 evaluated.
        # Latest week distribution: 良好28 / 稳定29 / 需要关注11 / 重点关注4.
        # Need-attention count per stage: 22 / 21 / 19 / 18 / 15 -> improving.
        # Department spread: 产品部 2关注+1重点, 数据平台部 not all flagged.
        # ------------------------------------------------------------------
        stages = [today - timedelta(days=28), today - timedelta(days=21), today - timedelta(days=14), today - timedelta(days=7), today]
        attention_limits = [22, 21, 19, 18, 15]  # 关注类人数每周递减
        attention_pool = [10, 11, 57, 58, 66, 67, 69, 46, 47, 0, 28, 20, 29, 65, 38, 54, 8, 70]
        critical_pool = [12, 59, 68, 1]
        flagged_indices = set(attention_pool + critical_pool)
        good_indices = set(range(0, 34)) - flagged_indices          # 28 人
        evaluated = user_ids[:72]
        good_users = set(user_ids[index] for index in good_indices)
        for stage_index, period_end in enumerate(stages):
            period_start = period_end - timedelta(days=6)
            attention_count = attention_limits[stage_index] - len(critical_pool)
            attention_users = set(user_ids[index] for index in attention_pool[:attention_count])
            critical_users = set(user_ids[index] for index in critical_pool)
            flagged = attention_users | critical_users
            for user_id in evaluated:
                if user_id in good_users:
                    level, score = "良好", RNG.randint(72, 88)
                elif user_id in critical_users:
                    level, score = "重点关注", RNG.randint(16, 30)
                elif user_id in attention_users:
                    level, score = "需要关注", RNG.randint(32, 48)
                else:
                    level, score = "稳定", RNG.randint(52, 68)
                session.add(
                    HealthRiskScore(
                        user_id=user_id,
                        period_start=period_start,
                        period_end=period_end,
                        risk_score=score,
                        risk_level=level,
                        main_factors=[risk_type for risk_type in ("sleep", "exercise", "stress") if RNG.random() < 0.5],
                    )
                )
        await session.flush()
        print(f"health_risk_scores: {len(evaluated) * len(stages)}")

        # ------------------------------------------------------------------
        # Risk assessments (overlapping, 5 types), 30d window
        # ------------------------------------------------------------------
        risk_records = 0
        for department_name, distributions in DEPARTMENT_RISKS.items():
            dept_users = [user for user in users if user.department == department_name]
            for risk_type, count in distributions:
                chosen = RNG.sample(dept_users, min(count, len(dept_users)))
                for user in chosen:
                    level = RNG.choice(["low", "medium", "low", "medium", "high"])
                    label, description, recommendation = RISK_META[risk_type]
                    session.add(
                        RiskAssessment(
                            user_id=user.id,
                            risk_type=risk_type,
                            level=level,
                            description=f"{label}：{description}",
                            recommendation=recommendation,
                            source=RNG.choice(["Wearable", "HealthCheck", "MentalCheckin"]),
                            assessed_at=datetime.combine(today - timedelta(days=RNG.randint(0, 29)), datetime.min.time()),
                        )
                    )
                    risk_records += 1
        await session.flush()
        print(f"risk_assessments: {risk_records}")

        # ------------------------------------------------------------------
        # Exam reports + indicators: 45 reports, 20 with >=1 abnormal item.
        # Abnormal employees are spread across departments: 产品部 gets 3.
        # ------------------------------------------------------------------
        report_user_ids = user_ids[:45]
        abnormal_indices = [10, 11, 12, 0, 1, 2, 56, 57, 58, 46, 47, 28, 29, 30, 66, 67, 38, 39, 20, 73]
        abnormal_user_ids = set(user_ids[index] for index in abnormal_indices)
        for user_id in report_user_ids:
            report_date = today - timedelta(days=RNG.randint(1, 29))
            report = HealthCheckReport(
                user_id=user_id,
                report_name="年度体检报告",
                hospital=RNG.choice(["市第一人民医院", "仁济健康体检中心", "安信体检门诊"]),
                report_date=report_date,
                parse_status="analyzed",
            )
            session.add(report)
            await session.flush()
            is_abnormal = user_id in abnormal_user_ids
            item_count = RNG.randint(8, 12)
            for _ in range(item_count):
                category, code, item_name, unit, ref_min, ref_max = RNG.choice(EXAM_ITEMS)
                if is_abnormal:
                    abnormal = RNG.random() < 0.55
                else:
                    abnormal = RNG.random() < 0.08
                if abnormal:
                    flag = RNG.choice(["high", "low"])
                    value = (ref_max or ref_min) * RNG.uniform(1.15, 1.8) if flag == "high" else (ref_min or 1.0) * RNG.uniform(0.4, 0.85)
                    value = round(value, 2)
                else:
                    flag = "normal"
                    low = ref_min or 0.0
                    high = ref_max or (ref_min or 10.0) * 2
                    value = round(RNG.uniform(low, high), 2)
                session.add(
                    HealthCheckIndicator(
                        report_id=report.id,
                        category=category,
                        code=code,
                        item_name=item_name,
                        value=value,
                        unit=unit,
                        value_text=str(value),
                        reference_min=ref_min,
                        reference_max=ref_max,
                        reference_text=f"{ref_min}-{ref_max}" if ref_min else f"<{ref_max}",
                        flag=flag,
                    )
                )
        await session.flush()
        print(f"health_reports: {len(report_user_ids)}")

        # ------------------------------------------------------------------
        # Health plans + tasks: 48 users (active 32 / completed 16)
        # ------------------------------------------------------------------
        plan_user_ids = user_ids[:48]
        for plan_index, user_id in enumerate(plan_user_ids):
            plan_type, plan_code, goal = PLAN_TYPES[plan_index % len(PLAN_TYPES)]
            is_active = plan_user_ids.index(user_id) < 32
            duration = RNG.randint(7, 21)
            start_date = today - timedelta(days=RNG.randint(1, 35))
            end_date = start_date + timedelta(days=duration)
            plan = HealthPlan(
                user_id=user_id,
                plan_name=f"{plan_type}计划",
                plan_type=plan_code,
                goal=goal,
                duration_days=duration,
                start_date=start_date,
                end_date=end_date,
                status="active" if is_active else "completed",
                source_agent="health_plan_agent",
                source_input={"type": plan_code},
            )
            session.add(plan)
            await session.flush()
            task_count = RNG.randint(3, 5)
            completion = RNG.uniform(0.4, 0.95)
            for day in range(task_count):
                completed = RNG.random() < completion
                session.add(
                    HealthPlanTask(
                        plan_id=plan.id,
                        user_id=user_id,
                        day_index=day + 1,
                        task_date=start_date + timedelta(days=day),
                        task_type=plan_code,
                        title=f"{plan_type}任务{day + 1}",
                        completion_status="completed" if completed else "pending",
                        completed_at=datetime.combine(start_date + timedelta(days=day), datetime.min.time()) if completed else None,
                    )
                )
        await session.flush()
        print(f"health_plans: {len(plan_user_ids)}")

        # ------------------------------------------------------------------
        # Mental checkins: 50 users, ~8-14 entries within 30 days
        # ------------------------------------------------------------------
        checkin_user_ids = user_ids[:50]
        checkin_count = 0
        moods = ["很好", "较好", "一般", "较差"]
        sleep_feelings = ["充足", "尚可", "一般", "不足"]
        for user_id in checkin_user_ids:
            entries = RNG.randint(8, 14)
            day_offsets = RNG.sample(range(0, 30), entries)  # unique days (unique user+date)
            for day_offset in day_offsets:
                session.add(
                    MentalCheckin(
                        user_id=user_id,
                        checkin_date=today - timedelta(days=day_offset),
                        mood=RNG.choice(moods),
                        stress_level=RNG.randint(1, 10),
                        energy_level=RNG.randint(1, 10),
                        sleep_feeling=RNG.choice(sleep_feelings),
                        stress_sources=RNG.sample(["工作", "生活", "睡眠", "家庭"], RNG.randint(0, 2)),
                    )
                )
                checkin_count += 1
        await session.flush()
        print(f"mental_checkins: {checkin_count}")

        await session.commit()
        print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())
