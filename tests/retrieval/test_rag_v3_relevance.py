from __future__ import annotations

import json
from pathlib import Path

from llm_ontology.ingestion.documents import materialize_for_collection
from llm_ontology.ingestion.loaders import NormalizedJsonlLoader
from llm_ontology.retrieval.config import load_rag_config
from llm_ontology.retrieval.models import (
    RetrievalHit,
    RetrievalRequest,
)
from llm_ontology.retrieval.pipeline import VectorRetriever
from llm_ontology.retrieval.query import build_retrieval_query
from llm_ontology.retrieval.reranking import CodeAwareReranker
from llm_ontology.retrieval.reranking import _parameter_count


def _write_record(path: Path, *, domain: str, input_code: str, output_code: str) -> None:
    path.write_text(
        json.dumps(
            {
                "domain": domain,
                "instruction": "Complete the Java task.",
                "input": input_code,
                "output": output_code,
                "source": "test-fixture",
                "context_level": "src_fm",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_v2_testing_embedding_indexes_only_input_but_keeps_pair_as_evidence(
    tmp_path: Path,
) -> None:
    input_code = "public int add(int left, int right) { return left + right; }"
    output_code = "@Test void addsNumbers() { assertEquals(3, add(1, 2)); }"
    path = tmp_path / "testing.jsonl"
    _write_record(
        path,
        domain="testing",
        input_code=input_code,
        output_code=output_code,
    )
    knowledge = next(
        iter(
            NormalizedJsonlLoader(
                path,
                dataset="testing-fixture",
                collection="testing_db",
            ).load_knowledge()
        )
    )

    document = materialize_for_collection(
        knowledge,
        "testing_db",
        embedding_template_version="2",
    )

    assert input_code in document.embedding_text
    assert output_code not in document.embedding_text
    assert input_code in document.content
    assert output_code in document.content
    assert document.metadata["embedding_text_template"] == "production_test_input"
    assert document.metadata["embedding_text_template_version"] == "2"


def test_v2_refactoring_embedding_indexes_only_original_code(
    tmp_path: Path,
) -> None:
    input_code = "public int total() { int x = 1; return x; }"
    output_code = "public int total() { return initialValue(); }"
    path = tmp_path / "refactoring.jsonl"
    _write_record(
        path,
        domain="refactoring",
        input_code=input_code,
        output_code=output_code,
    )
    knowledge = next(
        iter(
            NormalizedJsonlLoader(
                path,
                dataset="refactoring-fixture",
                collection="refactoring_db",
            ).load_knowledge()
        )
    )

    document = materialize_for_collection(
        knowledge,
        "refactoring_db",
        embedding_template_version="2",
    )

    assert input_code in document.embedding_text
    assert output_code not in document.embedding_text
    assert input_code in document.content
    assert output_code in document.content
    assert document.metadata["embedding_text_template"] == "refactoring_input"


def test_task_aware_query_adds_visible_semantics_without_reference_output() -> None:
    input_code = "public int add(int left, int right) { return left + right; }"
    query = build_retrieval_query(
        strategy="task_aware_v1",
        task="testing",
        input_text=input_code,
        requirements="Generate focused JUnit tests.",
        structured_identity={"class_name": "Calculator", "focal_method": "add"},
    )

    assert "Task: test generation" in query
    assert "Java class: Calculator" in query
    assert "Focal method: add" in query
    assert "Requirements: Generate focused JUnit tests." in query
    assert input_code in query
    assert "Corresponding test code" not in query


def test_code_aware_reranker_uses_input_side_not_reference_output() -> None:
    query = build_retrieval_query(
        strategy="task_aware_v1",
        task="testing",
        input_text=(
            "public int add(int left, int right) { return left + right; }"
        ),
        structured_identity={"class_name": "Calculator", "focal_method": "add"},
    )
    output_stuffed = RetrievalHit(
        document_id="output-stuffed",
        collection="testing_db",
        content=(
            "Task: test generation\n\n"
            "Production Java code:\npublic String align(String text) { return text; }\n\n"
            "Corresponding test code:\n"
            "Calculator calculator add add integer numbers left right"
        ),
        score=0.91,
    )
    relevant = RetrievalHit(
        document_id="relevant-input",
        collection="testing_db",
        content=(
            "Task: test generation\n\n"
            "Production Java code:\n"
            "public int add(int a, int b) { return a + b; }\n\n"
            "Corresponding test code:\n@Test void adds() {}"
        ),
        score=0.86,
    )

    ranked = CodeAwareReranker().rerank(query, [output_stuffed, relevant])

    assert [hit.document_id for hit in ranked] == ["relevant-input", "output-stuffed"]
    assert [hit.final_rank for hit in ranked] == [1, 2]


def test_parameter_count_ignores_commas_inside_java_generics() -> None:
    assert _parameter_count("Function<String, Integer> function") == 1
    assert _parameter_count("String name, Map<String, Integer> values") == 2


def test_retriever_fetches_larger_candidate_pool_before_top_three() -> None:
    class RecordingStore:
        def __init__(self) -> None:
            self.top_k: int | None = None

        def query(self, collection, query, *, top_k, where):
            self.top_k = top_k
            return [
                RetrievalHit(
                    document_id=f"doc-{index}",
                    collection=collection,
                    content=f"public int value{index}() {{ return {index}; }}",
                    score=1.0 - index / 100,
                )
                for index in range(8)
            ]

    store = RecordingStore()
    result = VectorRetriever(store).retrieve(
        RetrievalRequest(
            query="Task: testing\nProduction Java code:\npublic int value() { return 1; }",
            collections=["testing_db"],
            top_k=3,
            candidate_pool_size=12,
            reranking_strategy="code_aware_v1",
        )
    )

    assert store.top_k == 12
    assert len(result.documents) == 3
    assert len(result.trace.candidate_documents) == 8
    assert len(result.trace.retrieved_documents) == 3
    assert result.trace.candidate_pool_size == 12
    assert result.trace.reranking_strategy == "code_aware_v1"


def test_retriever_adds_exact_method_candidates_and_deduplicates_inputs() -> None:
    class HybridStore:
        def __init__(self) -> None:
            self.filters = []

        def query(self, collection, query, *, top_k, where):
            self.filters.append(where)
            exact_method_query = "method_name" in str(where)
            if exact_method_query:
                return [
                    RetrievalHit(
                        document_id="same-input-copy",
                        collection=collection,
                        content="public int add(int x, int y) { return x + y; }",
                        score=0.80,
                        metadata={"production_method_id": "same-input"},
                    ),
                    RetrievalHit(
                        document_id="second-add",
                        collection=collection,
                        content="public void add(String key, long value) { save(value); }",
                        score=0.70,
                        metadata={"production_method_id": "second-input"},
                    ),
                ]
            return [
                RetrievalHit(
                    document_id="unrelated",
                    collection=collection,
                    content=(
                        "public static int useFunction("
                        "Function<String, Integer> fn) { return fn.apply(\"x\"); }"
                    ),
                    score=0.99,
                ),
                RetrievalHit(
                    document_id="same-input-original",
                    collection=collection,
                    content="public int add(int x, int y) { return x + y; }",
                    score=0.75,
                    metadata={"production_method_id": "same-input"},
                ),
            ]

    store = HybridStore()
    query = build_retrieval_query(
        strategy="task_aware_v1",
        task="testing",
        input_text="public int add(int left, int right) { return left + right; }",
        structured_identity={"focal_method": "add"},
    )
    result = VectorRetriever(store).retrieve(
        RetrievalRequest(
            query=query,
            collections=["testing_db"],
            top_k=2,
            candidate_pool_size=3,
            reranking_strategy="code_aware_v1",
        )
    )

    assert len(store.filters) == 2
    assert "method_name" in str(store.filters[1])
    assert result.trace.candidates_before_deduplication == 4
    assert result.trace.candidates_after_deduplication == 3
    assert [hit.document_id for hit in result.documents] == [
        "same-input-original",
        "second-add",
    ]


def test_v3_config_keeps_a_separate_index_and_enables_relevance_pipeline() -> None:
    config = load_rag_config("configs/retrieval/ollama_bge_m3_v3.yaml")

    assert config.vector_store.persist_path.as_posix().endswith(
        "data/chroma/ollama_bge_m3_v3"
    )
    assert config.ingestion.pipeline_version == "rag-v3"
    assert config.ingestion.embedding_template_version == "2"
    assert config.retrieval.query_strategy == "task_aware_v1"
    assert config.retrieval.reranking_strategy == "code_aware_v1"
    assert config.retrieval.candidate_pool_size == 12
    assert config.retrieval.top_k == 3
