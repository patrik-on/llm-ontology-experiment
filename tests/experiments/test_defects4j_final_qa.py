from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from llm_ontology.benchmarks.defects4j import Defects4JConfig, verify_prepared_binding
from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.defects4j_runner import (
    build_dependency_identity, generation_failure_payload, report,
)
from llm_ontology.ingestion.manifest import DatasetManifest


def config(tmp_path, **kwargs):
    rag, hf = tmp_path / "rag.yaml", tmp_path / "hf.yaml"
    rag.write_text("config")
    hf.write_text("model config")
    return Defects4JConfig(defects4j_home=tmp_path, java_home=tmp_path, work_root=tmp_path,
                          junit_jar=tmp_path, junit_sha256="0"*64,
                          retrieval_config=rag, hf_models_config=hf, **kwargs)


def bound_fixture(tmp_path):
    path = tmp_path / "prepared.json"
    data = {"case": {"input_text": "original"}}
    write_json(path, data)
    manifest = DatasetManifest(dataset_name="defects4j", source_path=str(path), source_split="active",
                               usage_role="benchmark", allowed_for_indexing=False,
                               content_hash=file_sha256(path))
    write_json(tmp_path / "benchmark_manifest.json", manifest.model_dump(mode="json"))
    return path, data


def test_prepared_bytes_bound_even_if_internal_hash_is_recomputed(tmp_path):
    path, data = bound_fixture(tmp_path)
    verify_prepared_binding(data, path)
    data["case"]["input_text"] = "substituted"
    data["case_sha256"] = hashlib.sha256(json.dumps(data["case"], sort_keys=True).encode()).hexdigest()
    write_json(path, data)
    with pytest.raises(ValueError, match="digest"):
        verify_prepared_binding(data, path)


def test_manifest_rewrite_cannot_override_pinned_run_identity(tmp_path):
    path, data = bound_fixture(tmp_path)
    manifest_path = tmp_path / "benchmark_manifest.json"
    pinned = file_sha256(manifest_path)
    data["case"]["input_text"] = "substituted"
    write_json(path, data)
    manifest = json.loads(manifest_path.read_text())
    manifest["content_hash"] = file_sha256(path)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest changed"):
        verify_prepared_binding(data, path, expected_manifest_sha256=pinned)


def test_shared_dirty_source_bytes_and_membership_are_fingerprinted(tmp_path):
    selected = config(tmp_path)
    package = tmp_path / "source"
    paths = ["evaluation/inference_eval.py", "inference/prompting/canonical.py",
             "inference/structured_output.py", "inference/ollama_client.py",
             "retrieval/pipeline.py", "retrieval/token_budget.py"]
    for relative in paths:
        file = package / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("# original\n")
    original = build_dependency_identity(selected, source_root=package)
    for relative in paths:
        file = package / relative
        file.write_text("# dirty working bytes\n")
        changed = build_dependency_identity(selected, source_root=package)
        assert changed[str(file.resolve())] != original[str(file.resolve())]
        file.write_text("# original\n")
    extra = package / "untracked_shared.py"
    extra.write_text("# new source")
    assert build_dependency_identity(selected, source_root=package) != original


def test_same_run_rejects_shared_dependency_change_without_writing(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j_runner as module
    from llm_ontology.evaluation.run_layout import EvaluationRunLayout
    selected = config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "load_config", lambda path: selected)
    monkeypatch.setattr(module, "require_wsl", lambda: None)
    monkeypatch.setattr(module, "build_dependency_identity", lambda config: {"shared": "changed"})
    layout = EvaluationRunLayout("shared-change")
    layout.write_manifest(status="ready", metadata={"config": selected.model_dump(mode="json"),
                                                    "dependencies": {"shared": "original"}})
    before = layout.manifest_path.read_bytes()
    with pytest.raises(ValueError, match="Run/config mismatch"):
        module.main(["audit", "--run-id", "shared-change"])
    assert layout.manifest_path.read_bytes() == before


def test_shared_raw_schema_failure_persisted_and_kept_in_denominator(tmp_path):
    from llm_ontology.inference.experiment_runner import ExperimentCase, RagExperimentConfig, RagExperimentRunner
    from llm_ontology.inference.ollama_client import OllamaGenerationResult
    from llm_ontology.inference.structured_output import StructuredOutputError
    from llm_ontology.retrieval.models import RetrievalMode, RetrievalResult, RetrievalTrace
    from llm_ontology.retrieval.token_budget import CharacterTokenCounter
    sentinel = 'SENTINEL_RAW_INVALID_{"generated_tests":'
    class Provider:
        model_digest = "local-fixture"
        def generate_result(self, prompt, **kwargs):
            return OllamaGenerationResult(response=sentinel, model="fixture", eval_count=7, client_latency_ms=1)
    class Retriever:
        def retrieve(self, request):
            return RetrievalResult(documents=[], trace=RetrievalTrace(query=request.query))
    counter = CharacterTokenCounter()
    cfg = RagExperimentConfig(enabled=True, requested_task="testing", retrieval_mode=RetrievalMode.NO_RAG,
        dataset_version="fixture", embedding_model="none", embedding_revision="none", llm_model="fixture",
        tokenizer_model=counter.model_identifier, tokenizer_revision=counter.model_revision,
        token_counting_method=counter.method, total_context_tokens=8192, reserved_output_tokens=512,
        results_path=tmp_path / "results.jsonl", prompt_artifacts_dir=tmp_path / "prompts")
    runner = RagExperimentRunner(retriever=Retriever(), llm_provider=Provider(), token_counter=counter,
                                 total_context_tokens=8192, reserved_output_tokens=512, structured_retries=0)
    with pytest.raises(StructuredOutputError) as captured:
        runner.run_case(cfg, ExperimentCase(case_id="sentinel", instruction="test", input_text="class Input {}"))
    error = captured.value
    assert isinstance(error, RuntimeError)
    assert error.attempts[0].raw_response == sentinel
    assert error.attempts[0].generation_metadata["eval_count"] == 7
    shared = json.loads(Path(error.failure_metadata["failure_artifact_path"]).read_text())
    assert shared["structured_output_attempts"][0]["raw_response"] == sentinel
    root = tmp_path / "benchmark"
    failure = root / "predictions/rag_single/failure.json"
    write_json(failure, generation_failure_payload(error, case_sha256="case", arm="rag_single"))
    output = report(root)["arms"]["rag_single"]
    assert output["attempts"] == 1 and output["generated"] == 0
    assert output["unconditional_compilation_rate"] == 0
    assert output["generation_failure"]["structured_output_attempts"][0]["raw_response"] == sentinel


def test_cli_rejects_rehashed_prepared_before_mutating_manifest(tmp_path, monkeypatch):
    from llm_ontology.benchmarks import defects4j_runner as module
    from llm_ontology.evaluation.run_layout import EvaluationRunLayout
    selected = config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "load_config", lambda path: selected)
    monkeypatch.setattr(module, "require_wsl", lambda: None)
    layout = EvaluationRunLayout("prepared-tamper")
    layout.prepare()
    path, data = bound_fixture(layout.root.resolve())
    pins = {"prepared_sha256": file_sha256(path),
            "benchmark_manifest_sha256": file_sha256(path.parent / "benchmark_manifest.json")}
    layout.write_manifest(status="prepared", metadata={"config": selected.model_dump(mode="json"),
        "dependencies": build_dependency_identity(selected), "prepared_identity": pins})
    before = layout.manifest_path.read_bytes()
    data["case"]["input_text"] = "substitution"
    data["case_sha256"] = hashlib.sha256(json.dumps(data["case"], sort_keys=True).encode()).hexdigest()
    write_json(path, data)
    with pytest.raises(ValueError, match="Prepared bytes changed"):
        module.main(["audit", "--run-id", "prepared-tamper"])
    assert layout.manifest_path.read_bytes() == before
