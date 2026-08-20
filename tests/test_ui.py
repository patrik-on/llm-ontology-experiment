from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from llm_ontology.evaluation.experiment_log import ExperimentRecord
from llm_ontology.retrieval.config import RagConfig
from llm_ontology.retrieval.models import (
    RetrievalHit,
    RetrievalMode,
    RetrievalTrace,
)
from llm_ontology.ui.logging import capture_run_logs
from llm_ontology.ui.models import (
    EnvironmentStatus,
    UIRunRequest,
    mode_from_label,
    task_from_label,
)
from llm_ontology.ui.service import (
    ConfiguredInteractiveRunner,
    EnvironmentStatusService,
    UIService,
    UISettings,
)


class FakeEnvironmentService:
    def inspect(self) -> EnvironmentStatus:
        return EnvironmentStatus(
            ollama_status="available",
            configured_model="qwen:test",
            model_available=True,
            model_digest="sha256:test",
            chroma_path="fixture",
            chroma_status="available",
            embedding_model="fixture-embedding",
            embedding_revision="revision-1",
            python_version="3.12",
        )


class FakeRunner:
    model_name = "qwen:test"

    def __init__(self, record: ExperimentRecord | None = None, error: Exception | None = None) -> None:
        self.record = record
        self.error = error
        self.requests: list[UIRunRequest] = []

    def collection_for(self, task: str, mode: RetrievalMode) -> str | None:
        if mode == RetrievalMode.MULTI_COLLECTION_RAG:
            raise NotImplementedError("MultiRAG is not available yet.")
        return None if mode == RetrievalMode.NO_RAG else "mixed"

    def run(self, request: UIRunRequest) -> ExperimentRecord:
        self.requests.append(request)
        if self.error:
            raise self.error
        assert self.record is not None
        return self.record


def test_ui_label_mapping_uses_canonical_project_values() -> None:
    assert task_from_label("Testing") == "testing"
    assert task_from_label("Refactoring") == "refactoring"
    assert mode_from_label("Direct LLM") == RetrievalMode.NO_RAG
    assert mode_from_label("RAG") == RetrievalMode.SINGLE_COLLECTION_RAG
    assert mode_from_label("MultiRAG (Not available yet)") == RetrievalMode.MULTI_COLLECTION_RAG


def test_ui_request_rejects_blank_java_input() -> None:
    with pytest.raises(ValueError, match="Java input must not be empty"):
        UIRunRequest(task="testing", mode=RetrievalMode.NO_RAG, source_code="  ")


def test_configured_runner_does_not_create_chroma_storage_at_startup(
    tmp_path: Path,
) -> None:
    chroma_path = tmp_path / "missing-chroma"
    rag_config = RagConfig.model_validate(
        {
            "llm": {"provider": "mock", "model": "fixture-model"},
            "vector_store": {"persist_path": str(chroma_path)},
        }
    )

    ConfiguredInteractiveRunner(_settings(tmp_path), rag_config)

    assert not chroma_path.exists()


def test_ui_service_calls_injected_runner_once_without_retrieval_logic(tmp_path: Path) -> None:
    runner = FakeRunner(_record(tmp_path, mode=RetrievalMode.SINGLE_COLLECTION_RAG))
    service = _service(tmp_path, runner)

    result = service.run(
        task_label="Testing",
        mode_label="RAG",
        source_code="class Calculator {}",
        requirements="Generate edge-case tests.",
        top_k=7,
        log_level="INFO",
    )

    assert result.success is True
    assert len(runner.requests) == 1
    assert runner.requests[0].mode == RetrievalMode.SINGLE_COLLECTION_RAG
    assert runner.requests[0].top_k == 7
    assert runner.requests[0].requirements == "Generate edge-case tests."


def test_no_rag_view_explicitly_reports_retrieval_disabled(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeRunner(_record(tmp_path, mode=RetrievalMode.NO_RAG)))

    result = service.run(
        task_label="Testing",
        mode_label="Direct LLM",
        source_code="class A {}",
        requirements="",
        top_k=5,
        log_level="INFO",
    )

    assert result.retrieval_message == "Retrieval disabled."
    assert result.retrieval_documents == []
    assert result.output.code == "class ATest { @Test void works() {} }"


def test_retrieval_trace_is_transformed_without_score_percentages(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        FakeRunner(_record(tmp_path, mode=RetrievalMode.SINGLE_COLLECTION_RAG)),
    )

    result = service.run(
        task_label="Testing",
        mode_label="RAG",
        source_code="class A {}",
        requirements="",
        top_k=5,
        log_level="INFO",
    )

    document = result.retrieval_documents[0]
    assert document.rank == 1
    assert document.collection == "mixed"
    assert document.dataset_name == "methods2test"
    assert document.method_name == "calculate"
    assert document.score == pytest.approx(0.81)
    assert document.used_in_prompt is True


def test_metrics_view_uses_runner_metadata_and_na_for_missing_evaluation(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeRunner(_record(tmp_path, mode=RetrievalMode.NO_RAG)))

    result = service.run(
        task_label="Testing",
        mode_label="Direct LLM",
        source_code="class A {}",
        requirements="",
        top_k=5,
        log_level="INFO",
    )

    assert result.metrics.values["prompt_tokens"] == 120
    assert result.metrics.values["completion_tokens"] == 42
    assert result.metrics.values["generation_latency_ms"] == 25.5
    assert result.metrics.values["compile_success"] == "N/A"


def test_multirag_is_visible_but_returns_not_available(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeRunner())

    result = service.run(
        task_label="Testing",
        mode_label="MultiRAG (Not available yet)",
        source_code="class A {}",
        requirements="",
        top_k=5,
        log_level="INFO",
    )

    assert result.success is False
    assert "not available" in (result.error or "").lower()


def test_log_buffers_are_isolated_and_secrets_are_redacted() -> None:
    logger = logging.getLogger("llm_ontology.ui.test")
    with capture_run_logs("run-a", level="INFO") as first:
        logger.info("first token=private-value")
    with capture_run_logs("run-b", level="INFO") as second:
        logger.info("second")

    assert "first" in first.text()
    assert "private-value" not in first.text()
    assert "second" not in first.text()
    assert "second" in second.text()
    assert "first" not in second.text()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RuntimeError("Ollama is not reachable at http://localhost:11434"), "Ollama server unavailable"),
        (RuntimeError("Collection mixed does not exist"), "Chroma collection is missing"),
    ],
)
def test_expected_runtime_errors_are_user_friendly(
    tmp_path: Path, error: Exception, expected: str
) -> None:
    service = _service(tmp_path, FakeRunner(error=error))

    result = service.run(
        task_label="Testing",
        mode_label="Direct LLM",
        source_code="class A {}",
        requirements="",
        top_k=5,
        log_level="INFO",
    )

    assert result.success is False
    assert expected in (result.error or "")
    assert "Interactive run failed" in result.logs


def test_environment_status_service_is_read_only_and_reports_collections(tmp_path: Path) -> None:
    class FakeProvider:
        model_version = "fixture"

        def resolve_model_digest(self) -> str:
            return "sha256:fixture"

    class FakeCollection:
        name = "mixed"

        def count(self) -> int:
            return 12

    class FakeClient:
        def list_collections(self):
            return [FakeCollection()]

        def get_collection(self, *, name: str):
            assert name == "mixed"
            return FakeCollection()

    rag_config = RagConfig.model_validate(
        {
            "llm": {"provider": "mock", "model": "fixture-model"},
            "embeddings": {
                "model": "fixture-embedding",
                "revision": "revision-1",
            },
            "vector_store": {"persist_path": str(tmp_path)},
        }
    )
    status = EnvironmentStatusService(
        rag_config,
        llm_provider_factory=lambda settings: FakeProvider(),
        chroma_client_factory=lambda path: FakeClient(),
    ).inspect()

    assert status.model_available is True
    assert status.model_digest == "sha256:fixture"
    assert status.chroma_status == "available"
    assert status.collections[0].name == "mixed"
    assert status.collections[0].document_count == 12
    assert status.collections[0].manifest_status == "missing"


def _settings(tmp_path: Path) -> UISettings:
    return UISettings(
        retrieval_config=tmp_path / "rag.yaml",
        experiment_configs={
            "testing": {},
            "refactoring": {},
        },
        history_path=tmp_path / "history.jsonl",
        prompt_artifacts_dir=tmp_path / "prompts",
        default_instructions={
            "testing": "Generate tests.",
            "refactoring": "Refactor safely.",
        },
    )


def _service(tmp_path: Path, runner: FakeRunner) -> UIService:
    return UIService(_settings(tmp_path), runner, FakeEnvironmentService())  # type: ignore[arg-type]


def _record(tmp_path: Path, *, mode: RetrievalMode) -> ExperimentRecord:
    prompt_path = tmp_path / f"{mode.value}.txt"
    prompt_path.write_text("### Instruction\nGenerate tests.\n### Input\nclass A {}", encoding="utf-8")
    documents = []
    prompt_ids: list[str] = []
    selected_collections: list[str] = []
    if mode == RetrievalMode.SINGLE_COLLECTION_RAG:
        documents = [
            RetrievalHit(
                document_id="doc-1",
                collection="mixed",
                content="A related JUnit example.",
                score=0.81,
                metadata={
                    "document_type": "test_example",
                    "dataset": "methods2test",
                    "method_name": "calculate",
                    "source_uri": "fixture/Test.java",
                },
            )
        ]
        prompt_ids = ["doc-1"]
        selected_collections = ["mixed"]
    trace = RetrievalTrace(
        query="class A {}",
        selected_collections=selected_collections,
        retrieved_documents=documents,
        prompt_document_ids=prompt_ids,
        estimated_context_tokens=16 if documents else 0,
        total_latency_ms=3.5 if documents else 0.0,
    )
    return ExperimentRecord(
        configuration={},
        dataset_version="fixture-v1",
        embedding_model="fixture-embedding",
        embedding_version="revision-1",
        llm_model="qwen:test",
        llm_version="runtime_digest",
        retrieval_parameters={"top_k": 5},
        random_seed=42,
        input={"input_text": "class A {}"},
        retrieval_trace=trace,
        response=json.dumps(
            {
                "task_type": "testing",
                "analysis_summary": "Covers the happy path.",
                "generated_tests": "```java\nclass ATest { @Test void works() {} }\n```",
            }
        ),
        duration_ms=30.0,
        canonical_task="testing",
        retrieval_mode=mode.value,
        collection="mixed" if documents else None,
        llm_digest="sha256:test",
        prompt_artifact_path=str(prompt_path),
        prompt_hash="abc123",
        token_budget={
            "fixed_prompt_tokens": 50,
            "retrieval_tokens": 16 if documents else 0,
            "counting_method": "character_estimate_4_to_1",
        },
        structured_output_attempts=[
            {
                "attempt": 1,
                "raw_response": "{}",
                "validation_errors": [],
                "generation_metadata": {
                    "prompt_eval_count": 120,
                    "eval_count": 42,
                    "client_latency_ms": 25.5,
                },
            }
        ],
    )
