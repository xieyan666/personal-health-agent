"""Report Agent: turn parsed indicators + health profile into structured analysis.

Call chain (all data-driven, no re-parsing, no re-OCR):

    ReportTool (read health_report_items)
    + HealthProfileTool (read profile)     -> build_report_agent_user_prompt
    -> DeepSeek (structured JSON)
    -> Pydantic validation (one repair retry)
    -> Safety Guard
    -> ReportAnalysisResponse

Parser recognises, rule engine judges, agent explains.  The agent never
touches the original PDF and never recomputes laboratory flags.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.app.agent.health_supervisor.health_report_interpretation.prompt import (
    REPORT_AGENT_SYSTEM_PROMPT,
    build_report_agent_user_prompt,
)
from backend.app.exceptions import ServiceError
from backend.app.model_gateway.chat import ChatInput, chat_provider_for, normalize_chat_parameters
from backend.app.safety.report_analysis import guard_report_analysis
from backend.app.schemas.health_report_analysis import ReportAnalysisResponse

AGENT_NAME = "report_analysis_agent"
DEFAULT_MODEL_NAME = "deepseek-chat"
DEFAULT_MAX_TOKENS = 2048
MAX_REPAIR_RETRIES = 1


def _strip_markdown_fence(raw: str) -> str:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return fence.group(1) if fence else text


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = _strip_markdown_fence(raw)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Last resort: slice the first balanced {...} region.
        start, depth = text.find("{"), 0
        if start < 0:
            raise
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    value = json.loads(text[start : index + 1])
                    break
        else:
            raise
    if not isinstance(value, dict):
        raise ValueError("LLM output is not a JSON object")
    return value


class ReportAgent:
    """Stateless interpretation agent; instantiate per request."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.model_name = model_name or DEFAULT_MODEL_NAME
        self.max_tokens = max_tokens
        self.environment = environment
        self.last_model_used: str = DEFAULT_MODEL_NAME
        self.last_prompt_tokens: int = 0
        self.last_completion_tokens: int = 0

    def _provider(self):
        return chat_provider_for(
            "deepseek",
            secret_ref="env:DEEPSEEK_API_KEY",
            endpoint=None,
            environment=self.environment,
        )

    async def analyze(self, report_context: dict, profile: dict, knowledge_context: str = "") -> ReportAnalysisResponse:
        provider = self._provider()
        user_prompt = build_report_agent_user_prompt(report_context, profile, knowledge_context)
        system = REPORT_AGENT_SYSTEM_PROMPT
        raw_content: str | None = None
        for attempt in range(MAX_REPAIR_RETRIES + 1):
            messages = [ChatInput("system", system), ChatInput("user", user_prompt)]
            if attempt > 0:
                messages.append(
                    ChatInput(
                        "user",
                        "你上次的输出不是合法 JSON。请重新输出严格 JSON，不要包含任何解释文字、不要使用 Markdown 代码块。",
                    )
                )
            result = await self._chat(provider, messages)
            self.last_model_used = result.model or self.model_name
            self.last_prompt_tokens = result.prompt_tokens
            self.last_completion_tokens = result.completion_tokens
            raw_content = result.content
            try:
                payload = _parse_json_object(raw_content)
                analysis = ReportAnalysisResponse.model_validate(payload)
                return guard_report_analysis(analysis)
            except (ValueError, json.JSONDecodeError, Exception) as exc:
                if attempt < MAX_REPAIR_RETRIES:
                    continue
                raise ServiceError("AI 解读结果格式校验失败，请稍后重试") from exc
        raise ServiceError("AI 解读结果格式校验失败，请稍后重试")

    async def _chat(self, provider, messages):
        try:
            return await _run_in_thread(
                provider,
                messages,
                model_name=self.model_name,
                parameters=normalize_chat_parameters(
                    {"temperature": 0.3, "max_tokens": self.max_tokens}
                ),
            )
        except Exception as exc:
            raise ServiceError("AI 解读服务暂时不可用，请稍后重试") from exc


async def _run_in_thread(provider, messages, *, model_name, parameters):
    import asyncio

    return await asyncio.to_thread(
        provider.chat, list(messages), model_name=model_name, parameters=parameters
    )
