from __future__ import annotations

from typing import Any

from llm_ontology.retrieval.models import DocumentChunk, RetrievalHit
from llm_ontology.vectorstore.chroma import ChromaVectorStore
from llm_ontology.vectorstore.contracts import IndexWriteResult
from llm_ontology.vectorstore.manifest import CollectionManifest, CollectionManifestStore


class CollectionIndexLifecycle:
    """Explicit rebuild and compatibility boundary for persistent collections."""

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        manifest_store: CollectionManifestStore,
    ) -> None:
        self.vector_store = vector_store
        self.manifest_store = manifest_store

    def rebuild(
        self,
        manifest: CollectionManifest,
        documents: list[DocumentChunk],
    ) -> tuple[IndexWriteResult, CollectionManifest]:
        if any(document.collection != manifest.collection_name for document in documents):
            raise ValueError("Every document must target the rebuilt collection.")
        self.manifest_store.remove(manifest.collection_name)
        self._delete_exact_collection(manifest.collection_name)
        result = self.vector_store.add(manifest.collection_name, documents)
        completed = manifest.model_copy(update={"document_count": result.indexed})
        self.manifest_store.write(completed)
        return result, completed

    def query(
        self,
        expected_manifest: CollectionManifest,
        query: str,
        *,
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]:
        self.manifest_store.require_compatible(
            expected_manifest.collection_name, expected_manifest
        )
        return self.vector_store.query(
            expected_manifest.collection_name,
            query,
            top_k=top_k,
            where=where,
        )

    def _delete_exact_collection(self, collection_name: str) -> None:
        existing = {
            getattr(collection, "name", str(collection))
            for collection in self.vector_store.client.list_collections()
        }
        if collection_name in existing:
            self.vector_store.client.delete_collection(name=collection_name)
