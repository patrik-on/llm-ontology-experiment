from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm_ontology.approaches.contracts import RetrievedContext
from llm_ontology.benchmarks.testing_format_validation import (
    GOLD_CONTROL, fixture_case, load_protocol, summarize, verify_prepared,
)
from llm_ontology.inference.prompting.canonical import CanonicalPromptBuilder
from llm_ontology.inference.prompting.instruction import format_inference_prompt
from llm_ontology.inference.prompting.testing_full_class_v2 import (
    DEMO_PRODUCTION, DEMO_TEST, PROFILE, REQUIREMENTS, apply_profile, demo_answer,
)
from llm_ontology.inference.structured_output import TestingAnswer
from llm_ontology.retrieval.query import build_retrieval_query

FIXTURE = Path("data/validation/testing_full_class_v2/BatchSizer.java")


def test_demo_schema_and_same_substantive_example_all_envelopes():
    assert TestingAnswer.model_validate(demo_answer()).generated_tests == DEMO_TEST
    case = fixture_case(FIXTURE.read_text())
    ft, rag = [apply_profile(case, envelope=value) for value in ("ft", "rag")]
    for profiled in (ft, rag):
        assert REQUIREMENTS in profiled.instruction
        assert DEMO_PRODUCTION in profiled.instruction
        assert "ACTUAL TARGET FQN: validation.batches.BatchSizer" in profiled.instruction
        assert profiled.metadata["prompt_profile"] == PROFILE
    assert DEMO_TEST in ft.instruction
    assert json.dumps(demo_answer(), ensure_ascii=False, indent=2) in rag.instruction
    assert "Return only the complete Java test source" not in rag.instruction
    assert "Return only the canonical testing JSON" not in ft.instruction
    assert ft.input_text == rag.input_text == case.input_text
    assert case.instruction == ""  # explicit opt-in; no silent mutation


def test_single_multi_parity_and_gold_never_in_prompt_or_query():
    case = fixture_case(FIXTURE.read_text())
    case.metadata["expected_output"] = "EVALUATOR_ONLY_SENTINEL"
    case.metadata["gold"] = GOLD_CONTROL
    rag = apply_profile(case, envelope="rag")
    builder = CanonicalPromptBuilder()
    prompts = [builder.build(task="testing", instruction=rag.instruction, input_text=rag.input_text,
                approach=mode, contexts=(RetrievedContext(document_id="d", content="reference", source="s"),))
               for mode in ("rag", "multi_rag")]
    assert prompts[0].normalized_prompt_sha256 == prompts[1].normalized_prompt_sha256
    assert prompts[0].prompt_template_version == "canonical-se-prompt-v2"
    ft = apply_profile(case, envelope="ft")
    query = build_retrieval_query(strategy="task_aware_v1", task="testing", input_text=case.input_text,
                                  structured_identity=case.structured_identity)
    for prompt in [p.text for p in prompts] + [format_inference_prompt(ft.instruction, ft.input_text), query]:
        assert "BatchSizerControl" not in prompt
        assert "1073741824" not in prompt
        assert "EVALUATOR_ONLY_SENTINEL" not in prompt
        assert "NumberUtils" not in prompt
        assert "1.1L" not in prompt
    # Demonstration is instruction-only, not part of the retrieval input.
    assert "demo.labels" not in query
    assert "Focal method: groupsNeeded" in query


def test_explicit_target_and_envelope_required():
    case = fixture_case("class X {}")
    case.structured_identity.clear()
    with pytest.raises(ValueError, match="FQN"):
        apply_profile(case, envelope="ft")
    with pytest.raises(ValueError, match="envelope"):
        apply_profile(fixture_case("class X {}"), envelope="unknown")


def test_fixture_manifest_nonindexable_separate_from_demo_and_smoke():
    raw, runtime, manifest = load_protocol(Path("configs/benchmarks/testing_format_validation_v2.yaml"))
    assert runtime.max_new_tokens == 4096
    assert manifest.usage_role.value == "validation"
    assert manifest.case_count == 1
    with pytest.raises(ValueError, match="forbids indexing"):
        manifest.require_indexable()
    assert "smoke" not in raw["fixture"]
    assert "demo.labels" not in FIXTURE.read_text()


def test_failed_and_empty_results_retained_in_denominator(tmp_path):
    ft = tmp_path / "predictions/ft_testing"
    ft.mkdir(parents=True)
    (ft / "failure.json").write_text('{"status":"generation_failure"}')
    report = summarize(tmp_path)
    assert report["planned_arms"] == 3
    assert report["arms"]["ft_testing"]["attempted"] == 1
    assert report["arms"]["ft_testing"]["accepted"] is False
    assert report["arms"]["rag_single"]["planned"] == 1
    assert report["scientific_scores"] is False


@pytest.mark.parametrize(("executed", "truncated", "accepted"), [(0, False, False), (2, True, False), (2, False, True)])
def test_nonempty_execution_and_not_truncated_required(tmp_path, executed, truncated, accepted):
    out = tmp_path / "predictions/ft_testing"
    out.mkdir(parents=True)
    (out / "generation.json").write_text(json.dumps({"generation": {"output_truncated": truncated, "finish_reason": "eos"}}))
    metrics = tmp_path / "metrics/ft_testing"
    metrics.mkdir(parents=True)
    (metrics / "result.json").write_text(json.dumps({"status": "passed", "discovery": {"executed": executed}}))
    assert summarize(tmp_path)["arms"]["ft_testing"]["accepted"] is accepted


def test_prepared_data_binding_rejects_modified_file(tmp_path):
    (tmp_path / "prepared.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        verify_prepared(tmp_path, {"prepared_sha256": "0" * 64})


@pytest.mark.parametrize(("continuation", "reason"), [([4, 9], "eos"), ([4, 5], "length"), ([4], "stopped_unknown")])
def test_hf_generation_metadata_preserves_raw_counts_finish(monkeypatch, continuation, reason):
    import torch
    from llm_ontology.evaluation import inference_eval as module
    prompt_ids = torch.tensor([[1, 2]])
    monkeypatch.setattr(module, "encode_prompt", lambda *args: (prompt_ids, torch.ones_like(prompt_ids), "prompt"))
    captured = {}
    class Model:
        generation_config = SimpleNamespace(eos_token_id=9)
        def generate(self, **kwargs):
            captured.update(kwargs)
            return torch.tensor([[1, 2] + continuation])
    class Tokenizer:
        pad_token_id = 0
        eos_token_id = 9
        def decode(self, *args, **kwargs):
            return "  exact decoded continuation\n"
    prediction, meta = module.generate_prediction(Model(), Tokenizer(), "testing", "instruction", "source",
                                                  {"max_new_tokens": 2, "do_sample": False})
    assert prediction == "exact decoded continuation"
    assert meta["raw_response"] == "  exact decoded continuation\n"
    assert meta["input_tokens"] == 2 and meta["output_tokens"] == len(continuation)
    assert meta["finish_reason"] == reason
    assert meta["output_truncated"] is (reason == "length")
    assert "finish_reason" not in captured  # observation must not leak into generate arguments


def test_ollama_metadata_preserves_finish_reason_without_second_client():
    from llm_ontology.inference.ollama_client import OllamaProvider
    payload = {"response": "raw", "done": True, "done_reason": "length", "eval_count": 4096}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps(payload).encode()
    result = OllamaProvider(model_name="local", opener=lambda *args, **kwargs: Response()).generate_result("prompt")
    assert result.done_reason == "length" and result.eval_count == 4096 and result.done is True
