import pytest

from backend.app.model_gateway.embedding import FakeEmbeddingProvider, embedding_provider_for
from backend.app.services.exceptions import ValidationError


def test_fake_embedding_is_stable_and_fixed_dimension():
    provider = FakeEmbeddingProvider()
    first = provider.embed_texts(["hello"])[0]
    assert first == provider.embed_texts(["hello"])[0]
    assert len(first) == 8
    assert all(isinstance(value, float) for value in first)


def test_unknown_provider_type_is_rejected():
    with pytest.raises(ValidationError):
        embedding_provider_for("unknown")
