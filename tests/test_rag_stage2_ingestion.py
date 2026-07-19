from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from llm_ontology.core.task_mode import CanonicalTask, resolve_task
from llm_ontology.ingestion.corpus import ThreeCollectionCorpusBuilder
from llm_ontology.ingestion.documents import materialize_for_collection
from llm_ontology.ingestion.identity import (
    CaseIdentity,
    detect_leakage,
    make_sample_fingerprint,
)
from llm_ontology.ingestion.java import JavaAwareChunker, JavaParser, PairAwareJavaChunker
from llm_ontology.ingestion.loaders import NormalizedJsonlLoader, TextDocumentLoader
from llm_ontology.ingestion.manifest import DatasetManifest, UsageRole
from llm_ontology.ingestion.pdf_loader import PdfDocumentLoader
from llm_ontology.ingestion.pipeline import IndexingPipeline
from llm_ontology.retrieval.models import DocumentType, SourceDocument, make_document_chunk
from llm_ontology.providers.sentence_transformers import SentenceTransformerEmbeddingProvider
from llm_ontology.vectorstore.contracts import IndexWriteResult
from llm_ontology.vectorstore.manifest import (
    CollectionManifest,
    CollectionManifestStore,
    IncompatibleCollectionError,
)
from llm_ontology.vectorstore.lifecycle import CollectionIndexLifecycle


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


def _manifest(
    *,
    role: UsageRole = UsageRole.RETRIEVAL,
    allowed: bool = True,
    source_path: str = "data.jsonl",
) -> DatasetManifest:
    return DatasetManifest(
        dataset_name="sample",
        dataset_version="v1",
        source_path=source_path,
        source_split="train",
        usage_role=role,
        allowed_for_indexing=allowed,
        sample_count=1,
        content_hash="a" * 64,
    )


def test_task_aliases_preserve_canonical_project_names() -> None:
    assert resolve_task("refactor").canonical == CanonicalTask.REFACTORING
    assert resolve_task("test_generation").canonical == CanonicalTask.TESTING
    assert resolve_task("testing").requested == "testing"


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        (_manifest(allowed=False), "forbids indexing"),
        (_manifest(role=UsageRole.BENCHMARK), "not indexable"),
    ],
)
def test_ingestion_rejects_manifest_before_store_write(manifest, message) -> None:
    source = SourceDocument(
        content="content",
        embedding_text="content",
        document_type=DocumentType.LITERATURE,
        collection="mixed",
        source="source",
        dataset="sample",
        split="train",
        source_uri="source:1",
    )
    loader = type("Loader", (), {"load": lambda self: [source]})()
    chunker = type("Chunker", (), {"chunk": lambda self, document: [make_document_chunk(document)]})()
    store = RecordingStore()

    with pytest.raises(ValueError, match=message):
        IndexingPipeline(store).run(loader, chunker, manifest=manifest)

    assert store.documents == []


def test_leakage_detects_same_focal_input_when_full_documents_differ() -> None:
    identity = CaseIdentity(dataset="retrieval", case_id="one")
    code = "public int add(int a, int b) { return a + b; }"
    indexed = make_sample_fingerprint(
        identity=identity,
        input_code=code,
        focal_method_code=code,
        full_document=code + " reference output",
    )
    benchmark = make_sample_fingerprint(
        identity=CaseIdentity(dataset="benchmark", case_id="other"),
        input_code=code,
        focal_method_code=code,
        full_document=code,
    )

    report = detect_leakage(
        [indexed],
        [benchmark],
        indexed_manifest_id="retrieval-manifest",
        benchmark_manifest_id="benchmark-manifest",
    )

    assert not report.safe
    assert "input_code_hash" in report.overlaps[0].matched_by
    assert "focal_method_hash" in report.overlaps[0].matched_by


def test_embedding_text_and_ids_are_identical_across_collection_variants(tmp_path) -> None:
    path = tmp_path / "testing.jsonl"
    path.write_text(
        json.dumps(
            {
                "domain": "testing",
                "instruction": "Generate a test.",
                "input": "public int value() { return 1; }",
                "output": "@Test void valueIsOne() { assertEquals(1, value()); }",
                "source": "methods2test",
                "context_level": "src_fm",
            }
        )
        + chr(10),
        encoding="utf-8",
    )
    loader = NormalizedJsonlLoader(
        path,
        dataset="methods2test-v1",
        collection="tests",
        manifest=_manifest(source_path=path.as_posix()),
        expected_context_level="src_fm",
    )
    knowledge = next(iter(loader.load_knowledge()))
    tests_document = materialize_for_collection(knowledge, "tests")
    mixed_document = materialize_for_collection(knowledge, "mixed")

    tests_chunk = make_document_chunk(tests_document)
    mixed_chunk = make_document_chunk(mixed_document)

    assert tests_document.embedding_text == mixed_document.embedding_text
    assert tests_document.metadata["embedding_text_template_version"] == "1"
    assert tests_chunk.document_id == mixed_chunk.document_id
    assert tests_document.metadata["test_pair_id"]
    assert tests_document.metadata["context_level"] == "src_fm"


def test_java_parser_chunks_multiple_methods_with_imports_and_class_context() -> None:
    source = """package example;
import java.util.List;

public class Calculator {
    private int offset;

    /** Adds the configured offset. */
    @Deprecated
    public int add(int value) { return value + offset; }

    public void reset() { offset = 0; }
}
"""
    document = SourceDocument(
        content=source,
        embedding_text=source,
        document_type=DocumentType.PROJECT_CONTEXT,
        collection="mixed",
        source="repo",
        dataset="project-v1",
        split="train",
        language="java",
        source_uri="src/Calculator.java",
    )

    chunks = list(JavaAwareChunker().chunk(document))

    assert [chunk.metadata["method_name"] for chunk in chunks] == ["add", "reset"]
    assert all(chunk.metadata["parse_success"] for chunk in chunks)
    assert "import java.util.List;" in chunks[0].content
    assert "private int offset;" in chunks[0].content
    assert "/** Adds the configured offset. */" in chunks[0].content
    assert chunks[0].metadata["package_name"] == "example"
    assert chunks[0].metadata["parameter_types"] == ["int"]


def test_invalid_java_uses_traceable_whole_document_fallback() -> None:
    source = "public class Broken { public void method( {"
    document = SourceDocument(
        content=source,
        embedding_text=source,
        document_type=DocumentType.PROJECT_CONTEXT,
        collection="mixed",
        source="repo",
        dataset="project-v1",
        split="train",
        language="java",
        source_uri="src/Broken.java",
    )

    chunk = next(iter(JavaAwareChunker().chunk(document)))

    assert chunk.metadata["parse_success"] is False
    assert chunk.metadata["chunk_type"] == "whole_document_fallback"
    assert chunk.metadata["parse_failure_reason"]


def test_pair_aware_chunker_preserves_test_pair(tmp_path) -> None:
    path = tmp_path / "testing.jsonl"
    path.write_text(
        json.dumps(
            {
                "domain": "testing",
                "input": "public int value() { return 1; }",
                "output": "@Test public void valueIsOne() { assertEquals(1, value()); }",
                "context_level": "src_fm",
            }
        ),
        encoding="utf-8",
    )
    document = next(
        iter(
            NormalizedJsonlLoader(
                path,
                dataset="methods2test-v1",
                collection="tests",
                expected_context_level="src_fm",
            ).load()
        )
    )

    chunk = next(iter(PairAwareJavaChunker().chunk(document)))

    assert chunk.metadata["test_pair_id"] == document.metadata["test_pair_id"]
    assert chunk.metadata["chunk_type"] == "production_test_pair"
    assert chunk.metadata["parse_success"] is True
    assert chunk.metadata["synthetic_wrapper"] is True


def test_pdf_loader_keeps_pages_and_continues_after_corrupt_document(tmp_path) -> None:
    pdf_path = tmp_path / "literature.pdf"
    corrupt_path = tmp_path / "corrupt.pdf"
    _write_pdf(pdf_path)
    corrupt_path.write_bytes(b"not a pdf")
    manifest = _manifest(source_path=tmp_path.as_posix())
    loader = PdfDocumentLoader(
        [pdf_path, corrupt_path],
        dataset="literature-v1",
        collection="mixed",
        manifest=manifest,
    )

    documents = list(loader.load())

    assert len(documents) == 2
    assert [document.metadata["page_start"] for document in documents] == [1, 2]
    assert all("Shared Header" not in document.content for document in documents)
    assert all("Page #" not in document.content for document in documents)
    assert loader.report.loaded_documents == 1
    assert loader.report.failed_documents == 1
    assert loader.report.extracted_pages == 2
    assert loader.report.failures[0].source_path.endswith("corrupt.pdf")


def test_pdf_loader_refuses_path_outside_manifest(tmp_path) -> None:
    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    approved.mkdir()
    outside.mkdir()
    pdf_path = outside / "literature.pdf"
    _write_pdf(pdf_path)
    loader = PdfDocumentLoader(
        [pdf_path],
        dataset="literature-v1",
        collection="mixed",
        manifest=_manifest(source_path=approved.as_posix()),
    )

    with pytest.raises(ValueError, match="outside dataset manifest"):
        list(loader.load())


def test_three_collection_corpus_changes_only_cross_task_examples(tmp_path) -> None:
    refactoring_path = tmp_path / "refactoring.jsonl"
    testing_path = tmp_path / "testing.jsonl"
    literature_path = tmp_path / "literature.md"
    refactoring_path.write_text(
        json.dumps(
            {
                "domain": "refactoring",
                "input": "public int oldName() { return 1; }",
                "output": "public int betterName() { return 1; }",
                "refactoring_type": "Rename Method",
            }
        ),
        encoding="utf-8",
    )
    testing_path.write_text(
        json.dumps(
            {
                "domain": "testing",
                "input": "public int value() { return 1; }",
                "output": "@Test public void valueIsOne() { assertEquals(1, value()); }",
                "context_level": "src_fm",
            }
        ),
        encoding="utf-8",
    )
    literature_path.write_text(
        "# Rename Method\n\nA method name should communicate intent.",
        encoding="utf-8",
    )
    refactoring = list(
        NormalizedJsonlLoader(
            refactoring_path,
            dataset="refactoring-v1",
            collection="refactor",
        ).load_knowledge()
    )
    testing = list(
        NormalizedJsonlLoader(
            testing_path,
            dataset="testing-v1",
            collection="tests",
            expected_context_level="src_fm",
        ).load_knowledge()
    )
    literature = list(
        TextDocumentLoader(
            literature_path,
            dataset="literature-v1",
            collection="mixed",
        ).load_knowledge()
    )

    corpora = ThreeCollectionCorpusBuilder().build(
        refactoring=refactoring,
        testing=testing,
        literature=literature,
    )

    refactor_ids = {document.document_id for document in corpora["refactor"].documents}
    tests_ids = {document.document_id for document in corpora["tests"].documents}
    mixed_ids = {document.document_id for document in corpora["mixed"].documents}
    literature_id = next(
        document.document_id
        for document in corpora["mixed"].documents
        if document.document_type == DocumentType.LITERATURE
    )
    assert literature_id in refactor_ids
    assert literature_id in tests_ids
    assert refactor_ids < mixed_ids
    assert tests_ids < mixed_ids


def test_collection_manifest_rejects_stale_embedding_revision(tmp_path) -> None:
    store = CollectionManifestStore(tmp_path)
    actual = CollectionManifest(
        collection_name="tests",
        embedding_model="jinaai/jina-embeddings-v2-base-code",
        embedding_revision="old-revision",
        embedding_dimension=768,
        embedding_normalized=True,
        embedding_template_version="1",
        chunker_name="pair-aware-java",
        chunker_version="1",
        ingestion_pipeline_version="rag-v2",
        dataset_manifests=["methods2test-v1"],
        document_count=10,
        library_versions={"sentence-transformers": "5.6.0"},
    )
    expected = actual.model_copy(update={"embedding_revision": "new-revision"})
    store.write(actual)

    with pytest.raises(IncompatibleCollectionError, match="embedding_revision"):
        store.require_compatible("tests", expected)


def test_collection_lifecycle_writes_manifest_only_after_explicit_rebuild(tmp_path) -> None:
    class FakeClient:
        def list_collections(self):
            return []

    class FakeVectorStore:
        client = FakeClient()

        def add(self, collection_name, documents):
            assert collection_name == "tests"
            return IndexWriteResult(
                collection=collection_name,
                received=len(documents),
                indexed=len(documents),
                duplicates=0,
            )

    manifest_store = CollectionManifestStore(tmp_path)
    lifecycle = CollectionIndexLifecycle(FakeVectorStore(), manifest_store)  # type: ignore[arg-type]
    manifest = CollectionManifest(
        collection_name="tests",
        embedding_model="embedding",
        embedding_revision="revision",
        embedding_dimension=3,
        embedding_normalized=True,
        embedding_template_version="1",
        chunker_name="pair-aware-java",
        chunker_version="1",
        ingestion_pipeline_version="rag-v2",
        dataset_manifests=["dataset-manifest"],
        document_count=0,
    )

    result, completed = lifecycle.rebuild(manifest, [])

    assert result.indexed == 0
    assert manifest_store.read("tests") == completed


def test_sentence_transformer_provider_validates_empty_input_and_dimension() -> None:
    class FakeEmbeddings:
        def tolist(self):
            return [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]

    class FakeModel:
        def encode(self, texts, **kwargs):
            assert kwargs["normalize_embeddings"] is True
            return FakeEmbeddings()

    provider = SentenceTransformerEmbeddingProvider(
        model_identifier="local/test",
        model_revision="abc123",
        expected_dimension=3,
    )
    provider._model = FakeModel()

    assert len(provider.embed_documents(["one", "two"])) == 2
    with pytest.raises(ValueError, match="empty text"):
        provider.embed_query("   ")


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_EMBEDDING_TEST") != "1",
    reason="Opt-in model download/integration test.",
)
def test_real_jina_embedding_retrieval_sanity() -> None:
    provider = SentenceTransformerEmbeddingProvider(
        model_identifier="jinaai/jina-embeddings-v2-base-code",
        model_revision="516f4baf13dec4ddddda8631e019b5737c8bc250",
        remote_code_revision="3baf9e3ac750e76e8edd3019170176884695fb94",
        expected_dimension=768,
        device="cpu",
        batch_size=2,
        normalize_embeddings=True,
        max_sequence_length=512,
        trust_remote_code=True,
    )
    documents = provider.embed_documents(
        [
            "Extract Method refactors a long Java method into a named helper.",
            "A JUnit assertion verifies the expected return value.",
        ]
    )
    query = provider.embed_query("How can I refactor a long method?")
    scores = [sum(left * right for left, right in zip(query, document)) for document in documents]

    assert len(query) == 768
    assert scores[0] > scores[1]


def _write_pdf(path: Path) -> None:
    canvas = Canvas(str(path), pagesize=letter)
    for page_number, body in enumerate(
        (
            "Long Method is a code smell caused by excessive responsibilities.",
            "Extract Method moves a coherent fragment into a named method.",
        ),
        1,
    ):
        canvas.drawString(72, 750, "Shared Header")
        canvas.drawString(72, 700, body)
        canvas.drawString(72, 40, f"Page {page_number}")
        canvas.showPage()
    canvas.save()
