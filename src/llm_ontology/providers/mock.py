from __future__ import annotations

import hashlib
import math
import re


class DeterministicEmbeddingProvider:
    """Small offline embedding provider for tests and plumbing checks.

    It is deterministic and token-sensitive, but it is not a semantic model and
    must not be used for reported experiment results.
    """

    model_name = "deterministic-hash-embedding"
    model_version = "1"

    def __init__(self, dimension: int = 64) -> None:
        if dimension < 8:
            raise ValueError("Embedding dimension must be at least 8.")
        self.dimension = dimension

    @property
    def model_identifier(self) -> str:
        return self.model_name

    @property
    def model_revision(self) -> str:
        return self.model_version

    @property
    def embedding_dimension(self) -> int:
        return self.dimension

    def embed_documents(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


class MockLLMProvider:
    """Predictable LLM substitute used by automated tests and examples."""

    model_name = "mock-llm"
    model_version = "1"

    def __init__(self, response: str = '{"analysis_summary":"mock response"}') -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response
