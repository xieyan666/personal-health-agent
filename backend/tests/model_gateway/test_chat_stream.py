import pytest

from backend.app.model_gateway.chat import ChatInput, FakeChatProvider


@pytest.mark.asyncio
async def test_fake_stream_has_ordered_deltas_usage_and_done():
    events = [event async for event in FakeChatProvider().stream_chat([ChatInput("user", "hello")], model_name="fake-chat")]
    assert [event.type for event in events] == ["delta", "delta", "usage", "done"]
    assert "".join(event.content_delta for event in events if event.type == "delta") == "Fake assistant response: hello"
    assert events[-1].finish_reason == "stop"
