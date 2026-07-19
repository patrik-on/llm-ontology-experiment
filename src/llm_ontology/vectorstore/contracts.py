from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from llm_ontology.retrieval.models import DocumentChunk, RetrievalHit


class IndexWriteResult(BaseModel):
    collection: str
    received: int
    indexed: int
    duplicates: int


@runtime_checkable
class VectorStore(Protocol):
    def add(self, collection_name: str, documents: list[DocumentChunk]) -> IndexWriteResult:
        """Index documents while suppressing duplicate content hashes."""

    def query(
        self,
        collection_name: str,
        query: str,
        *,
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        """Retrieve documents from one physical collection."""
