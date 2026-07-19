from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-neutral text generation boundary."""

    model_name: str
    model_version: str

    def generate(self, prompt: str) -> str:
        """Generate one response for a fully rendered prompt."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Provider-neutral embedding boundary used outside ChromaDB."""

    model_name: str
    model_version: str
    dimension: int

    @property
    def model_identifier(self) -> str:
        """Stable provider model identifier."""

    @property
    def model_revision(self) -> str | None:
        """Pinned model revision when the provider supports one."""

    @property
    def embedding_dimension(self) -> int:
        """Number of values produced for one text."""

    def embed_documents(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[list[float]]:
        """Embed documents in input order."""

    def embed_query(self, text: str) -> list[float]:
        """Embed one retrieval query."""
