from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_ontology.core.task_mode import CanonicalTask
from llm_ontology.inference.experiment_runner import (
    ExperimentCase,
    RagExperimentConfig,
    RagExperimentRunner,
    load_experiment_config,
)
from llm_ontology.inference.ollama_client import OllamaGenerationResult, OllamaProvider
from llm_ontology.inference.structured_output import StructuredOutputGenerator
from llm_ontology.providers.mock import MockLLMProvider
from llm_ontology.retrieval.models import (
    RetrievalHit,
    RetrievalMode,
    RetrievalResult,
    RetrievalTrace,
)
from llm_ontology.retrieval.token_budget import (
    CharacterTokenCounter,
    ContextBudgeter,
    HuggingFaceTokenCounter,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_provider_sends_schema_and_records_runtime_metadata() -> None:
    captured: list[object] = []

    def opener(request: object, timeout: float) -> FakeResponse:
        captured.append(request)
        if request.full_url.endswith("/api/tags"):  # type: ignore[attr-defined]
            return FakeResponse({"models": [{"name": "qwen:7b", "digest": "sha256:abc"}]})
        return FakeResponse(
            {
                "model": "qwen:7b",
                "response": '{"ok":true}',
                "prompt_eval_count": 12,
                "eval_count": 5,
            }
        )

    provider = OllamaProvider(
        model_name="qwen:7b",
        context_window_tokens=32768,
        opener=opener,
    )
    assert provider.resolve_model_digest() == "sha256:abc"
    result = provider.generate_result("prompt", json_schema={"type": "object"})
    request_payload = json.loads(captured[-1].data.decode("utf-8"))  # type: ignore[attr-defined]

    assert request_payload["format"] == {"type": "object"}
    assert request_payload["options"]["seed"] == 42
    assert request_payload["options"]["num_ctx"] == 32768
    assert result.model_digest == "sha256:abc"
    assert result.prompt_eval_count == 12


def test_context_budget_tracks_truncation_with_explicit_fallback() -> None:
    budgeter = ContextBudgeter(
        CharacterTokenCounter(),
        total_context_tokens=20,
        reserved_output_tokens=4,
        safety_margin_tokens=2,
    )
    document = RetrievalHit(
        document_id="doc-1",
        collection="tests",
        content="x" * 80,
        score=1.0,
    )
    selection = budgeter.select("fixed", [document])

    assert selection.truncated_document_ids == ["doc-1"]
    assert selection.counting_method == "character_estimate_4_to_1"
    assert selection.retrieval_tokens <= 12


def test_context_budget_enforces_separate_retrieval_limit() -> None:
    budgeter = ContextBudgeter(
        CharacterTokenCounter(),
        total_context_tokens=100,
        reserved_output_tokens=10,
        safety_margin_tokens=5,
        retrieval_token_budget=8,
    )
    documents = [
        RetrievalHit(
            document_id="doc-1",
            collection="tests",
            content="x" * 80,
            score=1.0,
        )
    ]

    selection = budgeter.select("fixed", documents)

    assert selection.retrieval_token_budget == 8
    assert selection.retrieval_tokens <= 8
    assert selection.truncated_document_ids == ["doc-1"]


def test_context_budget_shortens_each_retrieved_document() -> None:
    budgeter = ContextBudgeter(
        CharacterTokenCounter(),
        total_context_tokens=100,
        reserved_output_tokens=10,
        safety_margin_tokens=5,
        max_document_tokens=5,
    )
    document = RetrievalHit(
        document_id="doc-long",
        collection="tests",
        content="x" * 80,
        score=1.0,
    )

    selection = budgeter.select("fixed", [document])

    assert selection.max_document_tokens == 5
    assert selection.retrieval_tokens == 5
    assert selection.documents[0].content == "x" * 20
    assert selection.truncated_document_ids == ["doc-long"]


@pytest.mark.parametrize(
    ("content", "input_heading", "input_sentinel", "output_heading", "output_sentinel"),
    [
        (
            "Task: test generation\n\n"
            "Methods2Test context level: src_fm\n\n"
            "Production Java code:\nINPUT_SENTINEL "
            + "i" * 800
            + "\n\nCorresponding test code:\nOUTPUT_SENTINEL "
            + "o" * 800,
            "Production Java code:",
            "INPUT_SENTINEL",
            "Corresponding test code:",
            "OUTPUT_SENTINEL",
        ),
        (
            "Task: refactoring\n\n"
            "Refactoring type: Extract Method\n\n"
            "Original Java code:\nINPUT_SENTINEL "
            + "i" * 800
            + "\n\nRefactored Java code:\nOUTPUT_SENTINEL "
            + "o" * 800
            + "\n\nChange summary or diff:\nignored when the pair needs compaction",
            "Original Java code:",
            "INPUT_SENTINEL",
            "Refactored Java code:",
            "OUTPUT_SENTINEL",
        ),
    ],
)
def test_context_budget_preserves_both_sides_of_paired_evidence(
    content: str,
    input_heading: str,
    input_sentinel: str,
    output_heading: str,
    output_sentinel: str,
) -> None:
    budgeter = ContextBudgeter(
        CharacterTokenCounter(),
        total_context_tokens=300,
        reserved_output_tokens=20,
        safety_margin_tokens=5,
        max_document_tokens=80,
    )
    document = RetrievalHit(
        document_id="paired-long",
        collection="mixed",
        content=content,
        score=1.0,
    )

    selection = budgeter.select("fixed", [document])

    compact = selection.documents[0].content
    assert input_heading in compact
    assert input_sentinel in compact
    assert output_heading in compact
    assert output_sentinel in compact
    assert budgeter.counter.count(compact) <= 80
    assert selection.truncated_document_ids == ["paired-long"]
    assert selection.pair_aware_truncated_document_ids == ["paired-long"]


def test_global_retrieval_budget_also_preserves_both_pair_sides() -> None:
    content = (
        "Task: test generation\n\n"
        "Production Java code:\nINPUT_SIDE "
        + "i" * 400
        + "\n\nCorresponding test code:\nOUTPUT_SIDE "
        + "o" * 400
    )
    budgeter = ContextBudgeter(
        CharacterTokenCounter(),
        total_context_tokens=200,
        reserved_output_tokens=20,
        safety_margin_tokens=5,
        retrieval_token_budget=60,
    )
    document = RetrievalHit(
        document_id="pair-global-budget",
        collection="testing_db",
        content=content,
        score=1.0,
    )

    selection = budgeter.select("fixed", [document])

    assert "INPUT_SIDE" in selection.documents[0].content
    assert "OUTPUT_SIDE" in selection.documents[0].content
    assert selection.retrieval_tokens <= 60
    assert selection.pair_aware_truncated_document_ids == ["pair-global-budget"]


def test_huggingface_counter_uses_token_ids_and_pinned_revision() -> None:
    class FakeTokenizer:
        def __call__(self, text: str, *, add_special_tokens: bool):
            assert add_special_tokens is False
            return {"input_ids": text.split()}

        def decode(self, token_ids, *, skip_special_tokens: bool):
            assert skip_special_tokens is True
            return " ".join(token_ids)

    counter = HuggingFaceTokenCounter(
        model_identifier="Qwen/test",
        model_revision="commit-1",
    )
    counter._tokenizer = FakeTokenizer()

    assert counter.count("one two three") == 3
    assert counter.truncate("one two three", 2) == "one two"
    assert counter.model_revision == "commit-1"


def test_structured_output_retries_only_invalid_format() -> None:
    class SequenceProvider(MockLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self.responses = [
                "not json",
                json.dumps(
                    {
                        "task_type": "testing",
                        "analysis_summary": "covers the branch",
                        "generated_tests": "@Test void works() {}",
                    }
                ),
            ]

        def generate(self, prompt: str) -> str:
            self.prompts.append(prompt)
            return self.responses.pop(0)

    provider = SequenceProvider()
    result = StructuredOutputGenerator(provider, max_retries=1).generate(
        "original", CanonicalTask.TESTING
    )

    assert result.answer.task_type == "testing"
    assert len(result.attempts) == 2
    assert "Repair only the JSON structure" in provider.prompts[1]


def test_experiment_matrix_rejects_cross_task_collection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="controlled cell"):
        _config(
            tmp_path,
            task="testing",
            mode=RetrievalMode.SINGLE_COLLECTION_RAG,
            collection="refactor",
        )
    with pytest.raises(ValueError, match="metadata RAG"):
        _config(tmp_path, task="testing", mode=RetrievalMode.METADATA_RAG, collection="tests")


def test_runner_records_alias_canonical_task_prompt_and_budget(tmp_path: Path) -> None:
    class NoRagRetriever:
        def retrieve(self, request):
            assert request.mode == RetrievalMode.NO_RAG
            return RetrievalResult(
                trace=RetrievalTrace(query=request.query, transformed_queries=[request.query])
            )

    response = json.dumps(
        {
            "task_type": "refactoring",
            "analysis_summary": "extract helper",
            "refactored_code": "void helper() {}",
        }
    )
    runner = RagExperimentRunner(
        retriever=NoRagRetriever(),
        llm_provider=MockLLMProvider(response),
        token_counter=CharacterTokenCounter(),
        total_context_tokens=2048,
        reserved_output_tokens=64,
    )
    record = runner.run_case(
        _config(tmp_path, task="refactor", mode=RetrievalMode.NO_RAG),
        ExperimentCase(
            case_id="case/1",
            instruction="Refactor the method.",
            input_text="void f() {}",
            structured_identity={"project": "p", "method": "f"},
        ),
    )

    assert record.requested_task == "refactor"
    assert record.canonical_task == "refactoring"
    assert record.collection is None
    assert record.prompt_hash
    assert record.prompt_template_version == "canonical-se-prompt-v2"
    assert record.prompt_template_sha256
    assert record.normalized_prompt_sha256
    assert record.full_prompt_sha256 == record.prompt_hash
    assert Path(record.prompt_artifact_path or "").exists()
    assert record.token_budget["counting_method"] == "character_estimate_4_to_1"
    assert record.generation_provider == "mock"
    assert record.generation_model == "fixture-llm"
    assert record.generation_model_digest is None


def test_runner_enforces_retrieval_budget_and_reports_runtime_prompt_count(
    tmp_path: Path,
) -> None:
    requests = []

    class NoRagRetriever:
        def retrieve(self, request):
            requests.append(request)
            return RetrievalResult(
                trace=RetrievalTrace(query=request.query, transformed_queries=[request.query])
            )

    class MetadataProvider:
        provider_name = "ollama"
        model_digest = None

        def generate(self, prompt: str) -> str:
            return self.generate_result(prompt).response

        def generate_result(self, prompt: str, *, json_schema=None):
            return OllamaGenerationResult(
                response=json.dumps(
                    {
                        "task_type": "testing",
                        "analysis_summary": "covers the target",
                        "generated_tests": "@Test void works() {}",
                    }
                ),
                model="fixture-llm",
                prompt_eval_count=1,
                client_latency_ms=1.0,
            )

    runner = RagExperimentRunner(
        retriever=NoRagRetriever(),
        llm_provider=MetadataProvider(),
        token_counter=CharacterTokenCounter(),
        total_context_tokens=2048,
        reserved_output_tokens=64,
        retrieval_token_budget=128,
        runtime_context_tokens=2048,
        fail_on_prompt_budget_exceeded=True,
    )
    config = _config(
        tmp_path,
        task="testing",
        mode=RetrievalMode.NO_RAG,
    ).model_copy(
        update={
            "retrieval_token_budget": 128,
            "metadata_filter": {"task": "testing"},
            "runtime_context_tokens": 2048,
            "fail_on_prompt_budget_exceeded": True,
        }
    )

    record = runner.run_case(
        config,
        ExperimentCase(
            case_id="runtime-audit",
            instruction="Generate tests.",
            input_text="final class Example { int value() { return 1; } }",
        ),
    )

    assert requests[0].max_context_tokens == 128
    assert requests[0].metadata_filter == {"task": "testing"}
    assert record.token_budget["retrieval_token_budget"] == 128
    assert record.token_budget["runtime_context_tokens"] == 2048
    assert record.token_budget["runtime_prompt_eval_count"] == 1
    assert record.token_budget["runtime_prompt_truncation_suspected"] is True


def test_eight_controlled_matrix_configs_are_valid_and_disabled() -> None:
    root = Path("configs/experiments/rag_v2")
    configs = [load_experiment_config(path) for path in sorted(root.glob("*.yaml"))]
    cells = {
        (
            config.canonical_task.value,  # type: ignore[union-attr]
            config.collection,
            tuple(config.collections),
        )
        for config in configs
    }

    assert len(configs) == 8
    assert cells == {
        ("refactoring", None, ()),
        ("refactoring", "refactoring_db", ()),
        ("refactoring", "mixed", ()),
        ("refactoring", None, ("testing_db", "refactoring_db")),
        ("testing", None, ()),
        ("testing", "testing_db", ()),
        ("testing", "mixed", ()),
        ("testing", None, ("testing_db", "refactoring_db")),
    }
    assert all(not config.enabled for config in configs)


def _config(
    root: Path,
    *,
    task: str,
    mode: RetrievalMode,
    collection: str | None = None,
) -> RagExperimentConfig:
    return RagExperimentConfig(
        enabled=True,
        requested_task=task,
        retrieval_mode=mode,
        collection=collection,
        dataset_version="fixture-v1",
        dataset_manifest_ids=["manifest-fixture"],
        embedding_model="fixture-embedding",
        embedding_revision="revision-1",
        llm_model="fixture-llm",
        tokenizer_model="character-estimate",
        tokenizer_revision="1",
        token_counting_method="character_estimate_4_to_1",
        total_context_tokens=2048,
        reserved_output_tokens=64,
        safety_margin_tokens=256,
        results_path=root / "records.jsonl",
        prompt_artifacts_dir=root / "prompts",
    )
