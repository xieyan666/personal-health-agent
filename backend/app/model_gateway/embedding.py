"""Embedding provider abstraction and deterministic local provider."""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import Sequence

from backend.app.exceptions import ValidationError


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic lexical-feature embedding for local/dev deployments.

    Text is reduced to character n-gram frequency hashed into a fixed-size
    bag, then L2-normalised.  Lexically related texts therefore receive a
    higher cosine score, which keeps the Retrieval -> Qdrant path meaningful
    without any external model.  Swap ``embedding_provider_for`` for a real
    provider (OpenAI / BGE / ...) when semantic embeddings are required; the
    rest of the pipeline is unchanged.
    """

    dimension = 8

    # Keep only CJK ideographs / Latin letters / digits: punctuation noise is
    # not a useful lexical signal for the 8-dim bag.
    _TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+")

    def _features(self, text: str) -> list[str]:
        tokens = self._TOKEN_RE.findall(text)
        grams: list[str] = []
        for token in tokens:
            if len(token) <= 2:
                grams.append(token)
                continue
            for index in range(len(token) - 1):
                grams.append(token[index : index + 2])
        return grams

    def _bucket(self, gram: str) -> int:
        return int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:4], 16) % self.dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for gram in self._features(text):
                vector[self._bucket(gram)] += 1.0
            norm = math.sqrt(sum(value * value for value in vector))
            if norm == 0.0:
                vectors.append([0.0] * self.dimension)
            else:
                vectors.append([round(value / norm, 8) for value in vector])
        return vectors


def embedding_provider_for(provider_type: str) -> EmbeddingProvider:
    if provider_type == "fake":
        return FakeEmbeddingProvider()
    raise ValidationError(f"Unsupported embedding provider: {provider_type}")
