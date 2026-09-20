"""Chat-model gateway abstractions and providers."""

from __future__ import annotations

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Any, AsyncIterator, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.app.exceptions import ServiceError, ValidationError

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_ENV_REF_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_CHAT_MAX_TOKENS = 1024
MIN_CHAT_MAX_TOKENS = 128
MAX_CHAT_MAX_TOKENS = 8192
MIN_TOOL_MAX_TOKENS = 256


def _validate_max_tokens(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("max_tokens must be an integer")
    if not MIN_CHAT_MAX_TOKENS <= value <= MAX_CHAT_MAX_TOKENS:
        raise ValidationError(f"max_tokens must be between {MIN_CHAT_MAX_TOKENS} and {MAX_CHAT_MAX_TOKENS}")
    return value


def normalize_chat_parameters(
    parameters: Mapping[str, Any] | None,
    *,
    max_tokens_override: int | None = None,
) -> dict[str, Any]:
    """Return one validated, provider-ready chat-generation parameter mapping."""
    if parameters is None:
        normalized: dict[str, Any] = {}
    elif isinstance(parameters, Mapping):
        normalized = dict(parameters)
    else:
        raise ValidationError("Chat parameters must be an object")

    if max_tokens_override is not None:
        normalized["max_tokens"] = _validate_max_tokens(max_tokens_override)
    elif "max_tokens" not in normalized:
        normalized["max_tokens"] = DEFAULT_CHAT_MAX_TOKENS
    else:
        normalized["max_tokens"] = _validate_max_tokens(normalized["max_tokens"])
    return normalized


def _json_value_type(value: Any) -> str:
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if value is None:
        return "null"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "other"


def tool_arguments_structure(arguments: Any) -> dict[str, Any]:
    """Return only non-content metadata for an invalid tool-arguments response."""
    metadata: dict[str, Any] = {
        "arguments_python_type": type(arguments).__name__,
        "arguments_present": arguments is not None,
        "arguments_length": len(arguments) if isinstance(arguments, (str, bytes, bytearray, dict, list, tuple)) else None,
    }
    if not isinstance(arguments, str):
        return metadata
    value = arguments.strip()
    metadata.update(
        starts_with_lbrace=value.startswith("{"),
        ends_with_rbrace=value.endswith("}"),
        starts_with_quote=value.startswith('"'),
        ends_with_quote=value.endswith('"'),
        contains_newline="\n" in arguments or "\r" in arguments,
        contains_backslash="\\" in arguments,
        contains_single_quote="'" in arguments,
    )
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        metadata.update(decode1_success=False, decode1_type="other")
        return metadata
    metadata.update(decode1_success=True, decode1_type=_json_value_type(decoded))
    if not isinstance(decoded, str):
        return metadata
    try:
        decoded_twice = json.loads(decoded.strip())
    except (TypeError, json.JSONDecodeError):
        metadata.update(decode2_success=False, decode2_type="other")
        return metadata
    metadata.update(decode2_success=True, decode2_type=_json_value_type(decoded_twice))
    return metadata


def _invalid_tool_arguments(arguments: Any, exc: Exception | None = None) -> ValidationError:
    error = ValidationError("TOOL_ARGUMENTS_JSON_INVALID")
    # Diagnostics are intentionally structural only and consumed by the one-shot smoke script.
    error.arguments_structure = tool_arguments_structure(arguments)
    if exc is not None:
        error.__cause__ = exc
    return error


def parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Parse OpenAI-compatible function arguments without accepting Python literals."""
    value = arguments
    for _ in range(2):
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value.strip())
        except json.JSONDecodeError as exc:
            raise _invalid_tool_arguments(arguments, exc) from exc
    if isinstance(value, dict):
        return value
    raise _invalid_tool_arguments(arguments)


@dataclass(frozen=True)
class ChatInput:
    role: str
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple["ToolCall", ...] = ()


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str | None = None
    reasoning_content_present: bool = False
    tool_calls: tuple["ToolCall", ...] = ()


@dataclass(frozen=True)
class ChatStreamEvent:
    type: str
    content_delta: str = ""
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str | None = None
    tool_calls: tuple["ToolCall", ...] = ()


class ChatProvider(ABC):
    @abstractmethod
    def chat(self, messages: Sequence[ChatInput], *, model_name: str, parameters: Mapping[str, Any] | None = None, tools: Sequence[Mapping[str, Any]] | None = None) -> ChatResult:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(self, messages: Sequence[ChatInput], *, model_name: str, parameters: Mapping[str, Any] | None = None, tools: Sequence[Mapping[str, Any]] | None = None) -> AsyncIterator[ChatStreamEvent]:
        raise NotImplementedError


class FakeChatProvider(ChatProvider):
    """Network-free deterministic provider used by runtime tests."""

    def chat(self, messages: Sequence[ChatInput], *, model_name: str, parameters: Mapping[str, Any] | None = None, tools: Sequence[Mapping[str, Any]] | None = None) -> ChatResult:
        del parameters
        from backend.app.tools import ToolCall
        if tools and not any(item.role == "tool" for item in messages):
            user_content = next((item.content for item in reversed(messages) if item.role == "user"), "")
            agent_tool = next((item["function"]["name"] for item in tools if item.get("function", {}).get("name", "").startswith("agent__")), None)
            if agent_tool:
                return ChatResult("", model_name, tool_calls=(ToolCall("fake-agent-1", agent_tool, {"task": user_content}),))
            if "add_numbers" in user_content or "最终分值" in user_content:
                internal = next((item["function"]["name"] for item in tools if "add_numbers" in item.get("function", {}).get("name", "")), "add_numbers")
                values = (17, 25) if "最终分值" in user_content else (2, 3)
                return ChatResult("", model_name, tool_calls=(ToolCall("fake-add-1", internal, {"a": values[0], "b": values[1]}),))
            match = re.search(r"(\d+(?:\.\d+)?)\s*kg.*?(\d+(?:\.\d+)?)\s*cm", user_content, re.I)
            if "calculate_bmi" in user_content and match:
                return ChatResult("", model_name, tool_calls=(ToolCall("fake-bmi-1", "calculate_bmi", {"weight_kg": float(match.group(1)), "height_cm": float(match.group(2))}),))
        tool_content = next((item.content for item in reversed(messages) if item.role == "tool"), None)
        if tool_content:
            content = f"Fake assistant result: BMI {tool_content}"
            prompt_tokens = sum(len(item.content) for item in messages)
            return ChatResult(content, model_name, prompt_tokens, len(content), prompt_tokens + len(content))
        user_content = next((item.content for item in reversed(messages) if item.role == "user"), "")
        content = f"Fake assistant response: {user_content}"
        prompt_tokens = sum(len(item.content) for item in messages)
        completion_tokens = len(content)
        return ChatResult(content, model_name, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens)

    async def stream_chat(self, messages: Sequence[ChatInput], *, model_name: str, parameters: Mapping[str, Any] | None = None, tools: Sequence[Mapping[str, Any]] | None = None) -> AsyncIterator[ChatStreamEvent]:
        result = self.chat(messages, model_name=model_name, parameters=parameters, tools=tools)
        if result.tool_calls:
            yield ChatStreamEvent(type="tool_calls", model=model_name, tool_calls=result.tool_calls)
            yield ChatStreamEvent(type="done", model=model_name, finish_reason="tool_calls")
            return
        for chunk in (result.content[:12], result.content[12:]):
            if chunk:
                yield ChatStreamEvent(type="delta", content_delta=chunk, model=model_name)
        yield ChatStreamEvent(type="usage", model=model_name, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens, total_tokens=result.total_tokens)
        yield ChatStreamEvent(type="done", model=model_name, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens, total_tokens=result.total_tokens, finish_reason="stop")


class DeepSeekChatProvider(ChatProvider):
    """Minimal non-streaming DeepSeek Chat Completions provider."""

    def __init__(self, *, secret_ref: str | None, endpoint: str | None = None, environment: Mapping[str, str] | None = None, request_opener: Callable[..., Any] = urlopen, timeout_seconds: float = 30.0) -> None:
        self.secret_ref = secret_ref
        self.endpoint = endpoint or DEFAULT_DEEPSEEK_BASE_URL
        self.environment = environment if environment is not None else os.environ
        self.request_opener = request_opener
        self.timeout_seconds = timeout_seconds

    def _api_key(self) -> str:
        if not self.secret_ref or not self.secret_ref.startswith("env:"):
            raise ValidationError("DeepSeek secret_ref must use the env:VARIABLE format")
        variable = self.secret_ref.removeprefix("env:")
        if not _ENV_REF_PATTERN.fullmatch(variable):
            raise ValidationError("DeepSeek secret_ref contains an invalid environment variable name")
        api_key = self.environment.get(variable)
        if not api_key:
            raise ServiceError("DeepSeek API key environment variable is not configured")
        return api_key

    def _url(self) -> str:
        base_url = self.endpoint.rstrip("/")
        return base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    @staticmethod
    def _request_parameters(parameters: Mapping[str, Any] | None) -> dict[str, Any]:
        if not parameters:
            return {}
        return {key: parameters[key] for key in ("temperature", "max_tokens", "thinking") if key in parameters}

    def chat(self, messages: Sequence[ChatInput], *, model_name: str, parameters: Mapping[str, Any] | None = None, tools: Sequence[Mapping[str, Any]] | None = None) -> ChatResult:
        if not model_name or not model_name.strip():
            raise ValidationError("DeepSeek model_name must not be empty")
        serialized_messages = []
        for item in messages:
            entry = {"role": item.role, "content": item.content}
            if item.tool_call_id: entry["tool_call_id"] = item.tool_call_id
            if item.tool_calls: entry["tool_calls"] = [{"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments)}} for call in item.tool_calls]
            serialized_messages.append(entry)
        payload: dict[str, Any] = {"model": model_name, "messages": serialized_messages, "stream": False}
        if tools: payload.update({"tools": list(tools), "tool_choice": "auto"})
        payload.update(self._request_parameters(parameters))
        request = Request(self._url(), data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"}, method="POST")
        started = perf_counter()
        try:
            with self.request_opener(request, timeout=self.timeout_seconds) as response:
                raw_response = response.read()
        except HTTPError as exc:
            raise ServiceError("DeepSeek API request failed") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ServiceError("DeepSeek API is unavailable") from exc
        try:
            response_data = json.loads(raw_response.decode("utf-8"))
            choice = response_data["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
        except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServiceError("DeepSeek API returned an invalid response") from exc
        if not isinstance(content, str):
            raise ServiceError("DeepSeek API returned an invalid response")
        from backend.app.tools import ToolCall
        if choice.get("finish_reason") == "length" and message.get("tool_calls"):
            raise ValidationError("TOOL_CALL_TRUNCATED")
        calls = []
        for call in message.get("tool_calls") or []:
            try:
                calls.append(ToolCall(str(call["id"]), str(call["function"]["name"]), parse_tool_arguments(call["function"].get("arguments"))))
            except ValidationError as exc:
                exc.provider_response_structure = {
                    "finish_reason": choice.get("finish_reason"),
                    "model": str(response_data.get("model") or model_name),
                }
                raise exc
            except (KeyError, TypeError) as exc:
                raise ValidationError("TOOL_ARGUMENTS_JSON_INVALID") from exc
        usage = response_data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        return ChatResult(content=content, model=str(response_data.get("model") or model_name), prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=int(usage.get("total_tokens") or prompt_tokens + completion_tokens), latency_ms=int((perf_counter() - started) * 1000), finish_reason=choice.get("finish_reason"), reasoning_content_present=bool(message.get("reasoning_content")), tool_calls=tuple(calls))

    async def stream_chat(self, messages: Sequence[ChatInput], *, model_name: str, parameters: Mapping[str, Any] | None = None, tools: Sequence[Mapping[str, Any]] | None = None) -> AsyncIterator[ChatStreamEvent]:
        if not model_name or not model_name.strip():
            raise ValidationError("DeepSeek model_name must not be empty")
        serialized_messages = []
        for item in messages:
            entry = {"role": item.role, "content": item.content}
            if item.tool_call_id: entry["tool_call_id"] = item.tool_call_id
            if item.tool_calls: entry["tool_calls"] = [{"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments)}} for call in item.tool_calls]
            serialized_messages.append(entry)
        payload: dict[str, Any] = {"model": model_name, "messages": serialized_messages, "stream": True, "stream_options": {"include_usage": True}}
        if tools: payload.update({"tools": list(tools), "tool_choice": "auto"})
        payload.update(self._request_parameters(parameters))
        request = Request(self._url(), data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"}, method="POST")
        try:
            response = await asyncio.to_thread(self.request_opener, request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            raise ServiceError("DeepSeek API request failed") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ServiceError("DeepSeek API is unavailable") from exc
        try:
            collected: dict[int, dict[str, str]] = {}
            while True:
                raw_line = await asyncio.to_thread(response.readline)
                if not raw_line:
                    break
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    choice = (chunk.get("choices") or [{}])[0]
                    raw_delta = choice.get("delta") or {}
                    delta = raw_delta.get("content") or ""
                    usage = chunk.get("usage") or {}
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ServiceError("DeepSeek API returned an invalid stream response") from exc
                if delta:
                    yield ChatStreamEvent(type="delta", content_delta=delta, model=chunk.get("model") or model_name)
                for item in raw_delta.get("tool_calls") or []:
                    index = int(item.get("index") or 0)
                    entry = collected.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    entry["id"] += str(item.get("id") or "")
                    function = item.get("function") or {}
                    entry["name"] += str(function.get("name") or "")
                    entry["arguments"] += str(function.get("arguments") or "")
                if usage:
                    yield ChatStreamEvent(type="usage", model=chunk.get("model") or model_name, prompt_tokens=int(usage.get("prompt_tokens") or 0), completion_tokens=int(usage.get("completion_tokens") or 0), total_tokens=int(usage.get("total_tokens") or 0))
                if choice.get("finish_reason"):
                    if collected:
                        if choice.get("finish_reason") == "length":
                            raise ValidationError("TOOL_CALL_TRUNCATED")
                        from backend.app.tools import ToolCall
                        try:
                            calls = tuple(ToolCall(value["id"], value["name"], parse_tool_arguments(value["arguments"])) for _, value in sorted(collected.items()))
                        except ValidationError as exc:
                            raise exc
                        except TypeError as exc:
                            raise ValidationError("TOOL_ARGUMENTS_JSON_INVALID") from exc
                        yield ChatStreamEvent(type="tool_calls", model=chunk.get("model") or model_name, tool_calls=calls)
                    yield ChatStreamEvent(type="done", model=chunk.get("model") or model_name, finish_reason=choice.get("finish_reason"))
        finally:
            await asyncio.to_thread(response.close)


def chat_provider_for(provider_type: str, *, secret_ref: str | None = None, endpoint: str | None = None, environment: Mapping[str, str] | None = None, request_opener: Callable[..., Any] = urlopen) -> ChatProvider:
    if provider_type == "fake":
        return FakeChatProvider()
    if provider_type == "deepseek":
        return DeepSeekChatProvider(secret_ref=secret_ref, endpoint=endpoint, environment=environment, request_opener=request_opener)
    raise ValidationError(f"Unsupported chat provider: {provider_type}")
