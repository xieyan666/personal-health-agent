import pytest

from backend.app.exceptions import ValidationError
from backend.app.model_gateway.chat import normalize_chat_parameters


def test_chat_token_budget_default_and_boundaries():
    assert normalize_chat_parameters({})["max_tokens"] == 1024
    assert normalize_chat_parameters({"max_tokens": 128})["max_tokens"] == 128
    assert normalize_chat_parameters({"max_tokens": 1024})["max_tokens"] == 1024
    assert normalize_chat_parameters({"max_tokens": 8192})["max_tokens"] == 8192


@pytest.mark.parametrize("value", [127, 8193, "1024", 1024.0, True, None])
def test_chat_token_budget_rejects_invalid_explicit_values(value):
    with pytest.raises(ValidationError):
        normalize_chat_parameters({"max_tokens": value})


def test_chat_token_budget_runtime_override_has_precedence():
    assert normalize_chat_parameters({"max_tokens": 1024}, max_tokens_override=512)["max_tokens"] == 512
    assert normalize_chat_parameters({}, max_tokens_override=512)["max_tokens"] == 512
    with pytest.raises(ValidationError):
        normalize_chat_parameters({}, max_tokens_override=127)
