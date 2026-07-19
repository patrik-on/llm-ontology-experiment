from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from llm_ontology.retrieval.models import DocumentChunk, SourceDocument


@runtime_checkable
class DocumentLoader(Protocol):
    def load(self) -> Iterable[SourceDocument]:
        """Load normalized source documents without indexing side effects."""


@runtime_checkable
class ChunkingStrategy(Protocol):
    def chunk(self, document: SourceDocument) -> Iterable[DocumentChunk]:
        """Split one source document into deterministic retrieval units."""
