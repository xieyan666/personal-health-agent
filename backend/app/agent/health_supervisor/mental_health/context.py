"""Consent-gated context builder for Mental Health Agent consultations.

This module deliberately passes only a selected assessment's result metadata
to the LLM.  Raw questionnaire answers remain in the authorised tool boundary.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.data_authorization_service import DataAccessNotAuthorized
from backend.app.tools.mental_health_trend import (
    get_authorized_mental_assessment_context,
    get_authorized_mental_health_trend_context,
)


MENTAL_ASSESSMENT_CONSENT_MESSAGE = (
    "如需结合你的心理自评历史进行个性化分析，需要先授权 AI 健康助手读取心理自评结果。"
    "你可以前往“数据授权”页面开启心理测评读取授权。"
)


async def build_mental_assessment_prompt(
    session: AsyncSession,
    *,
    user_id: UUID,
    assessment_id: UUID,
    declared_type: str,
    user_message: str,
) -> tuple[str | None, str | None]:
    """Return an LLM prompt or a safe user-facing response.

    Both selected assessment and optional trend access are audited by
    ``AuthorizationService`` through their tools.  A selected ID is the source
    of truth; the declared type is validated rather than trusted.
    """
    try:
        assessments = await get_authorized_mental_assessment_context(
            session,
            user_id,
            purpose="结合本次心理自评结果提供非诊断性支持建议",
            assessment_id=assessment_id,
        )
    except DataAccessNotAuthorized:
        return None, MENTAL_ASSESSMENT_CONSENT_MESSAGE

    assessment = assessments[0]
    if assessment["assessment_type"] != declared_type:
        # Do not allow a client to relabel a result from a different scale.
        return None, "本次心理测评信息不一致，请从对应测评结果页重新发起咨询。"

    if assessment.get("safety_flag"):
        # Preserve the PHQ-9 safety path instead of sending a normal analysis
        # request to the LLM when the approved safety rule was triggered.
        return None, (
            "我们注意到这次自评中有需要优先关注的内容。请先联系你信任的人、"
            "当地紧急服务或专业心理健康支持人员；如果你正处于紧急危险中，请立即寻求当地紧急帮助。"
        )

    try:
        trend = await get_authorized_mental_health_trend_context(
            session,
            user_id,
            purpose="结合近期心理状态趋势提供非诊断性支持建议",
        )
    except DataAccessNotAuthorized:
        trend = {"available": False, "note": "用户未授权读取心理状态趋势"}

    prompt = (
        "你是 Mental Health Agent，为企业员工提供非诊断性的心理健康支持。\n"
        "只能依据以下授权后的结构化结果，不得猜测原始题目答案或诊断疾病。"
        "请用温和、清晰的语言说明可关注的状态，并给出可执行的自我照护建议；"
        "如症状持续、加重或影响日常生活，建议寻求专业支持。\n"
        f"本次心理自评结果：{json.dumps(assessment, ensure_ascii=False)}\n"
        f"近期心理趋势（如已授权）：{json.dumps(trend, ensure_ascii=False)}\n"
        f"员工问题：{user_message}"
    )
    return prompt, None
