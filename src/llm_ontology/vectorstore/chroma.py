from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from llm_ontology.providers.contracts import EmbeddingProvider
from llm_ontology.retrieval.models import DocumentChunk, RetrievalHit
from llm_ontology.vectorstore.contracts import IndexWriteResult


LOGGER = logging.getLogger(__name__)


def create_chroma_client(persist_path: str | Path | None = None) -> Any:
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as exc:  # pragma: no cover - depends on optional installation.
        raise RuntimeError('ChromaDB is not installed. Install the "rag" project extra.') from exc

    settings = Settings(anonymized_telemetry=False)
    if persist_path is None:
        return chromadb.EphemeralClient(settings=settings)
    path = Path(persist_path)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path), settings=settings)


class ChromaVectorStore:
    """Thin ChromaDB adapter; embeddings remain owned by our provider boundary."""

    def __init__(self, client: Any, embedding_provider: EmbeddingProvider) -> None:
        self.client = client
        self.embedding_provider = embedding_provider

    def _collection(self, name: str) -> Any:
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def add(self, collection_name: str, documents: list[DocumentChunk]) -> IndexWriteResult:
        collection = self._collection(collection_name)
        unique: list[DocumentChunk] = []
        seen_hashes: set[str] = set()
        duplicates = 0
        for document in documents:
            if document.collection != collection_name:
                raise ValueError(
                    f"Document targets {document.collection!r}, not {collection_name!r}."
                )
            if document.content_hash in seen_hashes or self._contains_hash(
                collection, document.content_hash
            ):
                duplicates += 1
                continue
            seen_hashes.add(document.content_hash)
            unique.append(document)

        if unique:
            embeddings = self.embedding_provider.embed_documents(
                [document.embedding_text for document in unique]
            )
            collection.upsert(
                ids=[document.document_id for document in unique],
                embeddings=embeddings,
                documents=[document.content for document in unique],
                metadatas=[document.chroma_metadata() for document in unique],
            )
        LOGGER.info(
            "Indexed collection=%s received=%d indexed=%d duplicates=%d",
            collection_name,
            len(documents),
            len(unique),
            duplicates,
        )
        return IndexWriteResult(
            collection=collection_name,
            received=len(documents),
            indexed=len(unique),
            duplicates=duplicates,
        )

    def query(
        self,
        collection_name: str,
        query: str,
        *,
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        collection = self._collection(collection_name)
        kwargs: dict[str, Any] = {
            "query_embeddings": [self.embedding_provider.embed_query(query)],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = collection.query(**kwargs)
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits = [
            RetrievalHit(
                document_id=document_id,
                collection=collection_name,
                content=content or "",
                score=1.0 - float(distance),
                metadata=metadata or {},
            )
            for document_id, content, metadata, distance in zip(
                ids, documents, metadatas, distances, strict=True
            )
        ]
        LOGGER.info(
            "Retrieved collection=%s top_k=%d hits=%d filtered=%s",
            collection_name,
            top_k,
            len(hits),
            bool(where),
        )
        return hits

    @staticmethod
    def _contains_hash(collection: Any, content_hash: str) -> bool:
        result = collection.get(
            where={"content_hash": content_hash},
            limit=1,
            include=[],
        )
        return bool(result.get("ids"))
