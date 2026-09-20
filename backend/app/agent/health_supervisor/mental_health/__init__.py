"""Mental Health Agent: non-diagnostic mental wellness support.

V1 shell only (registered on the platform agents table with code
``mental_health_agent``).  Future responsibilities: work stress, emotional
support, stress management, energy state — always grounded in
MentalHealthTrendTool data and gated by Safety Guard.  Never diagnoses.
"""

from __future__ import annotations

AGENT_CODE = "mental_health_agent"
AGENT_NAME = "Mental Health Agent"
AGENT_CATEGORY = "health"
AGENT_DESCRIPTION = (
    "基于员工真实心理打卡数据（压力/情绪/精力）提供非诊断性的压力管理与心理健康支持建议，"
    "数据不足时必须明确说明，不做心理疾病诊断。"
)

# Reserved future input bundle (not implemented in v1).
MENTAL_AGENT_INPUT_SCHEMA = {
    "stress_avg_7d": 6.4,
    "stress_change": 0.8,
    "energy_avg_7d": 5.8,
    "mood_trend": "declining",
    "main_stress_sources": ["工作任务", "睡眠不足"],
    "checkin_count_7d": 6,
}

SAFETY_RULES = (
    "仅提供压力管理、作息、沟通与专业支持建议；"
    "禁止诊断抑郁症/焦虑症等心理疾病；"
    "出现明显高风险情况时引导用户寻求专业或紧急帮助。"
)
