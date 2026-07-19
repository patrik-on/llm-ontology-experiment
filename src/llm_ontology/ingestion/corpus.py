from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from llm_ontology.ingestion.chunkers import StructuredTextChunker
from llm_ontology.ingestion.documents import KnowledgeDocument, materialize_for_collection
from llm_ontology.ingestion.java import PairAwareJavaChunker
from llm_ontology.retrieval.models import DocumentChunk, DocumentType


class CollectionCorpus(BaseModel):
    model_config = ConfigDict(frozen=True)

    collection_name: str
    documents: list[DocumentChunk]


class ThreeCollectionCorpusBuilder:
    """Build the controlled specialized-vs-mixed experimental corpus matrix."""

    def __init__(
        self,
        *,
        pipeline_version: str = "rag-v2",
        literature_max_chars: int = 1800,
    ) -> None:
        self.pair_chunker = PairAwareJavaChunker(pipeline_version=pipeline_version)
        self.literature_chunker = StructuredTextChunker(
            max_chars=literature_max_chars,
            pipeline_version=pipeline_version,
        )

    def build(
        self,
        *,
        refactoring: list[KnowledgeDocument],
        testing: list[KnowledgeDocument],
        literature: list[KnowledgeDocument],
    ) -> dict[str, CollectionCorpus]:
        _require_document_types(refactoring, DocumentType.REFACTORING_EXAMPLE)
        _require_document_types(testing, DocumentType.TEST_EXAMPLE)
        _require_document_types(literature, DocumentType.LITERATURE)
        contents = {
            "refactor": [*refactoring, *literature],
            "tests": [*testing, *literature],
            "mixed": [*refactoring, *testing, *literature],
        }
        return {
            collection: CollectionCorpus(
                collection_name=collection,
                documents=self._materialize(documents, collection),
            )
            for collection, documents in contents.items()
        }

    def _materialize(
        self, documents: list[KnowledgeDocument], collection: str
    ) -> list[DocumentChunk]:
        chunks = []
        for knowledge_document in documents:
            source_document = materialize_for_collection(knowledge_document, collection)
            chunker = (
                self.literature_chunker
                if knowledge_document.document_type == DocumentType.LITERATURE
                else self.pair_chunker
            )
            chunks.extend(chunker.chunk(source_document))
        return chunks


def _require_document_types(
    documents: list[KnowledgeDocument], expected: DocumentType
) -> None:
    invalid = [document.document_type.value for document in documents if document.document_type != expected]
    if invalid:
        raise ValueError(
            f"Corpus expected only {expected.value!r} documents, received: {invalid}."
        )
