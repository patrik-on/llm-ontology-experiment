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
from llm_ontology.inference.ollama_client import OllamaProvider
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
            return FakeResponse(
                {"models": [{"name": "qwen:7b", "digest": "sha256:abc"}]}
            )
        return FakeResponse(
            {
                "model": "qwen:7b",
                "response": '{"ok":true}',
                "prompt_eval_count": 12,
                "eval_count": 5,
            }
        )

    provider = OllamaProvider(model_name="qwen:7b", opener=opener)
    assert provider.resolve_model_digest() == "sha256:abc"
    result = provider.generate_result("prompt", json_schema={"type": "object"})
    request_payload = json.loads(captured[-1].data.decode("utf-8"))  # type: ignore[attr-defined]

    assert request_payload["format"] == {"type": "object"}
    assert request_payload["options"]["seed"] == 42
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
        _config(tmp_path, task="testing", mode=RetrievalMode.SINGLE_COLLECTION_RAG, collection="refactor")
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
        total_context_tokens=512,
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
    assert Path(record.prompt_artifact_path or "").exists()
    assert record.token_budget["counting_method"] == "character_estimate_4_to_1"


def test_six_controlled_matrix_configs_are_valid_and_disabled() -> None:
    root = Path("configs/experiments/rag_v2")
    configs = [load_experiment_config(path) for path in sorted(root.glob("*.yaml"))]
    cells = {
        (config.canonical_task.value, config.collection)  # type: ignore[union-attr]
        for config in configs
    }

    assert len(configs) == 6
    assert cells == {
        ("refactoring", None),
        ("refactoring", "refactor"),
        ("refactoring", "mixed"),
        ("testing", None),
        ("testing", "tests"),
        ("testing", "mixed"),
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
        total_context_tokens=512,
        reserved_output_tokens=64,
        safety_margin_tokens=256,
        results_path=root / "records.jsonl",
        prompt_artifacts_dir=root / "prompts",
    )
