import pytest
from backend.app.model_gateway.chat import ChatInput, FakeChatProvider, parse_tool_arguments, tool_arguments_structure

def test_fake_provider_tool_round_trip_and_normal_chat():
    provider = FakeChatProvider()
    tools = [{"type": "function", "function": {"name": "calculate_bmi"}}]
    first = provider.chat([ChatInput("user", "请使用 calculate_bmi 工具计算 70kg、175cm 的 BMI")], model_name="fake", tools=tools)
    assert first.tool_calls[0].arguments == {"weight_kg": 70.0, "height_cm": 175.0}
    final = provider.chat([ChatInput("user", "x"), ChatInput("tool", '{"bmi": 22.86}', tool_call_id="fake-bmi-1")], model_name="fake", tools=tools)
    assert "22.86" in final.content
    assert not provider.chat([ChatInput("user", "hello")], model_name="fake").tool_calls

@pytest.mark.parametrize("value", [{"weight_kg": 70}, '{"weight_kg":70}', '"{\\"weight_kg\\":70}"', '  {"weight_kg":70}  '])
def test_tool_arguments_accepts_json_objects(value):
    assert parse_tool_arguments(value) == {"weight_kg": 70}

@pytest.mark.parametrize("value", ["{'weight_kg':70}", "[1]", "1", '"text"', "null"])
def test_tool_arguments_rejects_non_objects(value):
    with pytest.raises(Exception): parse_tool_arguments(value)


def test_invalid_tool_arguments_structure_is_content_free_and_classifies_two_decodes():
    metadata = tool_arguments_structure('"not-json-after-second-decode"')
    assert metadata["arguments_python_type"] == "str"
    assert metadata["arguments_present"] is True
    assert metadata["decode1_success"] is True
    assert metadata["decode1_type"] == "string"
    assert metadata["decode2_success"] is False
    assert "arguments" not in metadata
