"""Small health-assistant adapter over the existing model gateway."""

import asyncio
import os

from backend.app.exceptions import ServiceError
from backend.app.model_gateway.chat import ChatInput, chat_provider_for, normalize_chat_parameters

HEALTH_ASSISTANT_PROMPT = """你是一名企业员工健康管理AI助手。
你的任务是根据员工健康问题提供健康管理建议，帮助用户改善睡眠、饮食、运动和生活习惯，并使用通俗语言回答。
请在内部先判断意图：睡眠、饮食、运动、体检报告或健康风险问题分别采用对应专业建议；无法匹配时直接作为通用健康助手回答。不要向用户透露路由、Agent名称或内部处理过程。
注意：不进行疾病诊断，不替代医生；对明显高风险情况提醒用户寻求专业医疗帮助。"""


class LLMService:
    """Use the existing DeepSeek gateway without exposing credentials to callers."""

    def __init__(self, *, environment: dict[str, str] | None = None):
        self.environment = environment if environment is not None else os.environ

    async def answer(self, message: str) -> str:
        api_key = self.environment.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ServiceError("DeepSeek API is not configured")
        model_name = self.environment.get("DEEPSEEK_MODEL", "deepseek-chat")
        endpoint = self.environment.get("DEEPSEEK_BASE_URL") or None
        provider = chat_provider_for(
            "deepseek",
            secret_ref="env:DEEPSEEK_API_KEY",
            endpoint=endpoint,
            environment=self.environment,
        )
        result = await asyncio.to_thread(
            provider.chat,
            [ChatInput("system", HEALTH_ASSISTANT_PROMPT), ChatInput("user", message)],
            model_name=model_name,
            parameters=normalize_chat_parameters({"temperature": 0.7, "max_tokens": 1024}),
        )
        if not result.content.strip():
            raise ServiceError("DeepSeek returned an empty answer")
        return result.content

    async def stream_answer(self, message: str):
        """Yield provider deltas for the health assistant SSE endpoint."""
        api_key = self.environment.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ServiceError("DeepSeek API is not configured")
        provider = chat_provider_for("deepseek", secret_ref="env:DEEPSEEK_API_KEY", endpoint=self.environment.get("DEEPSEEK_BASE_URL") or None, environment=self.environment)
        async for event in provider.stream_chat(
            [ChatInput("system", HEALTH_ASSISTANT_PROMPT), ChatInput("user", message)],
            model_name=self.environment.get("DEEPSEEK_MODEL", "deepseek-chat"),
            parameters=normalize_chat_parameters({"temperature": 0.7, "max_tokens": 1024}),
        ):
            if event.type == "delta" and event.content_delta:
                yield event.content_delta
