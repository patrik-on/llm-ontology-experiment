from __future__ import annotations

import logging
from collections import defaultdict

from pydantic import BaseModel, Field

from llm_ontology.ingestion.contracts import ChunkingStrategy, DocumentLoader
from llm_ontology.ingestion.manifest import DatasetManifest
from llm_ontology.vectorstore.contracts import IndexWriteResult, VectorStore


LOGGER = logging.getLogger(__name__)


class IndexingReport(BaseModel):
    loaded_documents: int
    produced_chunks: int
    writes: list[IndexWriteResult] = Field(default_factory=list)
    manifest_id: str | None = None
    fallback_chunks: int = 0

    @property
    def indexed(self) -> int:
        return sum(write.indexed for write in self.writes)

    @property
    def duplicates(self) -> int:
        return sum(write.duplicates for write in self.writes)


class IndexingPipeline:
    """Leakage-safe orchestration between loaders, chunkers and vector stores."""

    def __init__(self, vector_store: VectorStore, allowed_splits: list[str] | None = None) -> None:
        self.vector_store = vector_store
        self.allowed_splits = set(allowed_splits or ["train"])

    def run(
        self,
        loader: DocumentLoader,
        chunker: ChunkingStrategy,
        *,
        manifest: DatasetManifest | None = None,
    ) -> IndexingReport:
        if manifest is not None:
            manifest.require_indexable()
        source_documents = list(loader.load())
        disallowed = sorted({document.split for document in source_documents} - self.allowed_splits)
        if disallowed:
            values = ", ".join(disallowed)
            LOGGER.warning("Refusing indexing request for disallowed splits: %s", values)
            raise ValueError(
                f"Refusing to index disallowed split(s): {values}. "
                f"Allowed splits: {', '.join(sorted(self.allowed_splits))}."
            )

        by_collection = defaultdict(list)
        for source_document in source_documents:
            by_collection[source_document.collection].extend(chunker.chunk(source_document))

        fallback_chunks = sum(
            1
            for chunks in by_collection.values()
            for chunk in chunks
            if chunk.metadata.get("parse_success") is False
        )

        writes = [
            self.vector_store.add(collection, chunks)
            for collection, chunks in sorted(by_collection.items())
        ]
        report = IndexingReport(
            loaded_documents=len(source_documents),
            produced_chunks=sum(len(chunks) for chunks in by_collection.values()),
            writes=writes,
            manifest_id=manifest.manifest_id if manifest else None,
            fallback_chunks=fallback_chunks,
        )
        LOGGER.info(
            "Indexing complete loaded=%d chunks=%d indexed=%d duplicates=%d fallbacks=%d",
            report.loaded_documents,
            report.produced_chunks,
            report.indexed,
            report.duplicates,
            report.fallback_chunks,
        )
        return report
