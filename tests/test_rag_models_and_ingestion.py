from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from llm_ontology.ingestion import (
    IndexingPipeline,
    NormalizedJsonlLoader,
    PassthroughChunker,
    StructuredTextChunker,
    TextDocumentLoader,
)
from llm_ontology.retrieval.config import CollectionSettings, load_rag_config
from llm_ontology.retrieval.models import DocumentType, SourceDocument, make_document_chunk
from llm_ontology.vectorstore.contracts import IndexWriteResult


class RecordingStore:
    def __init__(self) -> None:
        self.documents = []

    def add(self, collection_name, documents):
        self.documents.extend(documents)
        return IndexWriteResult(
            collection=collection_name,
            received=len(documents),
            indexed=len(documents),
            duplicates=0,
        )

    def query(self, collection_name, query, *, top_k, where=None):
        return []


def test_rag_config_loads_named_collections() -> None:
    config = load_rag_config("configs/retrieval/base.yaml")

    assert config.collections.resolve("test_examples") == "test_examples"
    assert config.ingestion.allowed_splits == ["train"]
    assert config.embeddings.provider == "deterministic_mock"
    assert config.llm.provider == "mock"


def test_collection_names_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        CollectionSettings(test_examples="same", refactoring_examples="same")


def test_document_ids_and_hashes_are_deterministic() -> None:
    document = SourceDocument(
        content="class Example { }\n",
        embedding_text="class Example { }",
        document_type=DocumentType.PROJECT_CONTEXT,
        collection="project_context",
        source="repo",
        dataset="sample",
        source_uri="src/Example.java",
    )

    first = make_document_chunk(document)
    second = make_document_chunk(document.model_copy(update={"content": "class Example { }\r\n"}))

    assert first.content_hash == second.content_hash
    assert first.document_id == second.document_id


def test_normalized_loader_preserves_record_and_domain_metadata(tmp_path) -> None:
    path = tmp_path / "train.jsonl"
    record = {
        "instruction": "Generate a test.",
        "input": "public int add(int a, int b) { return a + b; }",
        "output": "@Test void adds() { assertEquals(3, add(1, 2)); }",
        "domain": "testing",
        "source": "methods2test",
        "context_level": "src_fm",
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    documents = list(
        NormalizedJsonlLoader(
            path,
            dataset="methods2test-v1",
            collection="test_examples",
        ).load()
    )

    assert len(documents) == 1
    assert documents[0].document_type == DocumentType.TEST_EXAMPLE
    assert documents[0].metadata["context_level"] == "src_fm"
    assert "Corresponding test code:\n@Test" in documents[0].content


def test_structured_text_loader_and_chunker_keep_source_reference(tmp_path) -> None:
    path = tmp_path / "literature.md"
    path.write_text("# Long Method\n\nDefinition text.\n\n## Extract Method\n\nRecommendation.", encoding="utf-8")
    document = next(
        iter(
            TextDocumentLoader(
                path,
                dataset="literature-v1",
                collection="software_engineering_literature",
            ).load()
        )
    )

    chunks = list(StructuredTextChunker(max_chars=200).chunk(document))

    assert chunks
    assert all(chunk.source_uri == path.as_posix() for chunk in chunks)
    assert chunks[0].metadata["title"] == "literature"


def test_indexing_refuses_non_train_split_before_store_write() -> None:
    source = SourceDocument(
        content="content",
        embedding_text="content",
        document_type=DocumentType.TEST_EXAMPLE,
        collection="test_examples",
        source="dataset",
        dataset="dataset-v1",
        split="test",
        language="java",
        task="testing",
        source_uri="test:1",
    )
    store = RecordingStore()

    with pytest.raises(ValueError, match="Refusing to index disallowed"):
        IndexingPipeline(store).run(type("Loader", (), {"load": lambda self: [source]})(), PassthroughChunker())

    assert store.documents == []
