from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm_ontology.retrieval.models import RetrievalHit, RetrievalRequest, RetrievalResult


@runtime_checkable
class Retriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Run an auditable retrieval operation."""


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, documents: list[RetrievalHit]) -> list[RetrievalHit]:
        """Return candidates in final relevance order."""
