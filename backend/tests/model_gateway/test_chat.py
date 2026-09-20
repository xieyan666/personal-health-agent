"""Offline tests for the chat provider gateway."""

from __future__ import annotations

import json

import pytest

from backend.app.exceptions import ServiceError, ValidationError
from backend.app.model_gateway.chat import (
    ChatInput,
    DeepSeekChatProvider,
    FakeChatProvider,
    chat_provider_for,
)


class _Response:
    def __init__(self, body: dict) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


def test_fake_chat_is_stable_and_returns_usage():
    provider = FakeChatProvider()
    messages = [ChatInput("user", "hello")]
    first = provider.chat(messages, model_name="fake-chat")
    second = provider.chat(messages, model_name="fake-chat")
    assert first == second
    assert first.content == "Fake assistant response: hello"
    assert first.total_tokens == first.prompt_tokens + first.completion_tokens


def test_chat_provider_factory_selects_fake_and_deepseek():
    assert isinstance(chat_provider_for("fake"), FakeChatProvider)
    assert isinstance(chat_provider_for("deepseek", secret_ref="env:DEEPSEEK_API_KEY"), DeepSeekChatProvider)
    with pytest.raises(ValidationError):
        chat_provider_for("unknown")


def test_deepseek_parses_response_and_only_forwards_supported_parameters():
    captured = {}

    def opener(request, *, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response({"model": "deepseek-chat", "choices": [{"message": {"content": "ok", "reasoning_content": "internal"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}})

    provider = DeepSeekChatProvider(secret_ref="env:DEEPSEEK_API_KEY", environment={"DEEPSEEK_API_KEY": "unit-test-only"}, endpoint="https://example.test", request_opener=opener)
    result = provider.chat([ChatInput("user", "hello")], model_name="deepseek-chat", parameters={"temperature": 0.2, "max_tokens": 32, "thinking": {"type": "disabled"}, "ignored": "value"})
    assert result.content == "ok"
    assert result.prompt_tokens == 3
    assert result.completion_tokens == 2
    assert result.total_tokens == 5
    assert result.finish_reason == "stop"
    assert result.reasoning_content_present is True
    assert captured["url"] == "https://example.test/chat/completions"
    assert captured["payload"] == {"model": "deepseek-chat", "messages": [{"role": "user", "content": "hello"}], "stream": False, "temperature": 0.2, "max_tokens": 32, "thinking": {"type": "disabled"}}


@pytest.mark.parametrize("secret_ref", [None, "literal:key", "env:not-valid"])
def test_deepseek_rejects_invalid_secret_reference(secret_ref):
    with pytest.raises(ValidationError):
        DeepSeekChatProvider(secret_ref=secret_ref, environment={}).chat([], model_name="deepseek-chat")


def test_deepseek_requires_configured_environment_secret():
    with pytest.raises(ServiceError, match="environment variable"):
        DeepSeekChatProvider(secret_ref="env:DEEPSEEK_API_KEY", environment={}).chat([], model_name="deepseek-chat")


def test_deepseek_rejects_truncated_nonstream_tool_call_before_argument_parsing():
    def opener(_request, *, timeout):
        del timeout
        return _Response({"model": "deepseek-chat", "choices": [{"message": {"content": "", "tool_calls": [{"id": "call-1", "function": {"name": "calculate_bmi", "arguments": "{"}}]}, "finish_reason": "length"}], "usage": {}})

    provider = DeepSeekChatProvider(secret_ref="env:DEEPSEEK_API_KEY", environment={"DEEPSEEK_API_KEY": "unit-test-only"}, endpoint="https://example.test", request_opener=opener)
    with pytest.raises(ValidationError, match="TOOL_CALL_TRUNCATED"):
        provider.chat([ChatInput("user", "tool")], model_name="deepseek-chat", tools=[{"type": "function", "function": {"name": "calculate_bmi"}}])


class _StreamResponse:
    def __init__(self, lines):
        self.lines = iter(lines)

    def readline(self):
        return next(self.lines, b"")

    def close(self):
        return None


@pytest.mark.asyncio
async def test_deepseek_rejects_truncated_stream_tool_call_before_execution():
    chunks = [
        b'data: {"model":"deepseek-chat","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1","function":{"name":"calculate_bmi","arguments":"{"}}]},"finish_reason":null}]}\n',
        b'data: {"model":"deepseek-chat","choices":[{"delta":{},"finish_reason":"length"}]}\n',
        b"data: [DONE]\n",
    ]

    def opener(_request, *, timeout):
        del timeout
        return _StreamResponse(chunks)

    provider = DeepSeekChatProvider(secret_ref="env:DEEPSEEK_API_KEY", environment={"DEEPSEEK_API_KEY": "unit-test-only"}, endpoint="https://example.test", request_opener=opener)
    with pytest.raises(ValidationError, match="TOOL_CALL_TRUNCATED"):
        async for _ in provider.stream_chat([ChatInput("user", "tool")], model_name="deepseek-chat", tools=[{"type": "function", "function": {"name": "calculate_bmi"}}]):
            pass
