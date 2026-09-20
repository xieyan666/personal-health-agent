"""Health Plan Agent: converts health advice into executable daily plans.

V1 shell only.  The agent is registered on the platform ``agents`` table with
code ``health_plan_agent``.  Its future input bundle (HealthProfileTool +
HealthTrendTool + RiskTool + ReportTool + MentalHealthTrendTool) and structured
output are documented below; plan generation will be wired to the AI health
assistant in a later iteration.
"""

from __future__ import annotations

AGENT_CODE = "health_plan_agent"
AGENT_NAME = "Health Plan Agent"
AGENT_CATEGORY = "health"
AGENT_DESCRIPTION = (
    "把健康建议转化为结构化、可执行的每日健康计划，"
    "输出 plan -> days -> tasks，供健康计划页面展示与执行。"
)

# Future structured input bundle (reserved, not implemented in v1).
PLAN_AGENT_INPUT_SCHEMA = {
    "goal": "改善睡眠",
    "profile": {"age": 23, "bmi": 20},
    "trend": {"sleep_avg_7d": 6.3, "exercise_avg": 32},
    "risk": {"sleep": "attention"},
}

# Future structured output (reserved, not implemented in v1).
PLAN_AGENT_OUTPUT_SCHEMA = {
    "name": "7天睡眠改善计划",
    "duration_days": 7,
    "goal": "改善睡眠",
    "days": [
        {"day": 1, "tasks": [{"title": "23:30前准备入睡", "type": "sleep"}, {"title": "步行20分钟", "type": "exercise"}]}
    ],
}
