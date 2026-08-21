from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from llm_ontology.ingestion.chunkers import StructuredTextChunker
from llm_ontology.ingestion.documents import KnowledgeDocument, materialize_for_collection
from llm_ontology.ingestion.java import JavaParser, PairAwareJavaChunker
from llm_ontology.retrieval.models import DocumentChunk, DocumentType


class CollectionCorpus(BaseModel):
    model_config = ConfigDict(frozen=True)

    collection_name: str
    documents: list[DocumentChunk]


class ProductionCorpusBuilder:
    """Build equivalent mixed and disjoint MultiRAG corpus views."""

    def __init__(
        self,
        *,
        pipeline_version: str = "rag-v2",
        literature_max_chars: int = 1800,
        mixed_collection: str = "mixed",
        testing_collection: str = "testing_db",
        refactoring_collection: str = "refactoring_db",
        literature_collection: str = "literature_db",
        pair_parser: JavaParser | None = None,
        embedding_template_version: str = "1",
    ) -> None:
        self.pair_chunker = PairAwareJavaChunker(
            pipeline_version=pipeline_version, parser=pair_parser
        )
        self.literature_chunker = StructuredTextChunker(
            max_chars=literature_max_chars,
            pipeline_version=pipeline_version,
        )
        self.mixed_collection = mixed_collection
        self.testing_collection = testing_collection
        self.refactoring_collection = refactoring_collection
        self.literature_collection = literature_collection
        self.embedding_template_version = embedding_template_version

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
            self.refactoring_collection: refactoring,
            self.testing_collection: testing,
            self.mixed_collection: [*refactoring, *testing, *literature],
        }
        if literature:
            contents[self.literature_collection] = literature
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
            source_document = materialize_for_collection(
                knowledge_document,
                collection,
                embedding_template_version=self.embedding_template_version,
            )
            chunker = (
                self.literature_chunker
                if knowledge_document.document_type == DocumentType.LITERATURE
                else self.pair_chunker
            )
            chunks.extend(chunker.chunk(source_document))
        return chunks


class ThreeCollectionCorpusBuilder(ProductionCorpusBuilder):
    """Legacy class name retained for compatibility; output is now disjoint."""


def _require_document_types(
    documents: list[KnowledgeDocument], expected: DocumentType
) -> None:
    invalid = [document.document_type.value for document in documents if document.document_type != expected]
    if invalid:
        raise ValueError(
            f"Corpus expected only {expected.value!r} documents, received: {invalid}."
        )
