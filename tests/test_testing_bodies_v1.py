import json

import pytest

from llm_ontology.benchmarks.defects4j_bodies_pilot import Ledger
from llm_ontology.core.task_mode import CanonicalTask
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting.testing_bodies_v1 import (
    BodyPromptBuilder, apply_profile, assemble, scaffold, validate_body,
)
from llm_ontology.inference.structured_output import (
    StructuredOutputError, StructuredOutputGenerator, TestingBodiesAnswer as Bodies,
)


def case():
    return ExperimentCase(case_id="synthetic", instruction="old full class",
        input_text="package demo;\nimport java.util.Locale;\npublic class Target {}",
        structured_identity={"class_name": "demo.Target", "method_name": "f"})


@pytest.mark.parametrize("body", ["", "// comment", "}", "} void other() {", "package x;",
    "import java.util.*;", "class Local {}", "void helper() {}", "new Object() {};",
    r"\u007d", "@Deprecated int x = 1;", "public class Whole {}"])
def test_reject_declaration_escape(body):
    with pytest.raises(ValueError):
        validate_body(body)


def test_deterministic_no_gold_or_logic():
    c = case()
    empty = scaffold(c)
    assert "assertEquals(" not in empty and "*;" not in empty
    assert "testCase1" in empty and "testCase2" in empty
    assert scaffold(c.model_copy(update={"metadata": {"gold": "SECRET"}})) == empty
    answer = Bodies(testCase1="int x = 2; assertEquals(2, x);", testCase2="assertThrows(Exception.class, () -> { throw new Exception(); });")
    source = assemble(empty, answer)
    assert source == assemble(empty, answer)
    assert answer.testCase1 in source and answer.testCase2 in source
    with pytest.raises(ValueError):
        assemble(source, answer)


def test_same_scaffold_and_substantive_prompt():
    c = apply_profile(case())
    builder = BodyPromptBuilder()
    direct = builder.build(task="testing", instruction=c.instruction, input_text=c.input_text,
        requirements=c.requirements, approach="direct")
    assert scaffold(case()) in direct.text
    assert "Generate one complete" not in direct.text
    assert "generated_tests" not in direct.text
    assert "SECRET" not in direct.text


@pytest.mark.parametrize("raw", ['{}', '{"testCase1":"x;"}', '{"testCase1":"x;","testCase2":"y;","extra":0}',
    'class Whole {}', '~~~json', '{"testCase1":1,"testCase2":"y;"}'])
def test_strict_retain_failure_and_no_retry(raw):
    class Provider:
        calls = 0
        def generate(self, prompt):
            self.calls += 1
            return raw
    provider = Provider()
    generator = StructuredOutputGenerator(provider, max_retries=0, answer_model=Bodies)
    with pytest.raises(StructuredOutputError) as error:
        generator.generate("prompt", CanonicalTask.TESTING)
    assert provider.calls == 1
    assert error.value.attempts[0].raw_response == raw


def test_ledger_exclusive_and_direct_gate(tmp_path):
    out = tmp_path / "predictions/qwen_base"
    out.mkdir(parents=True)
    ledger = Ledger(tmp_path, "qwen_base")
    ledger.charge({"one": "request"})
    with pytest.raises(FileExistsError):
        ledger.charge({"second": "request"})
    with pytest.raises(ValueError):
        Ledger(tmp_path, "rag_single").charge({})
    with pytest.raises(ValueError):
        Ledger(tmp_path, "unknown")
    assert len(list(tmp_path.glob("predictions/*/dispatch.json"))) == 1
    assert json.loads((out / "dispatch.json").read_text())["charged_to_budget"]



def test_all_four_arms_exclusive_cap(tmp_path, monkeypatch):
    import llm_ontology.benchmarks.defects4j_bodies_pilot as pilot
    monkeypatch.setattr(pilot, "usable", lambda root: True)
    for arm in pilot.ARMS:
        (tmp_path / "predictions" / arm).mkdir(parents=True)
        ledger = Ledger(tmp_path, arm)
        ledger.charge({"request": arm})
        with pytest.raises(FileExistsError):
            ledger.charge({"retry": arm})
    assert len(list(tmp_path.glob("predictions/*/dispatch.json"))) == 4


def test_http_failure_charged_and_error_retained(tmp_path, monkeypatch):
    from urllib.error import HTTPError
    from urllib.request import Request
    from io import BytesIO
    import llm_ontology.benchmarks.defects4j_bodies_pilot as pilot
    out = tmp_path / "predictions/qwen_base"
    out.mkdir(parents=True)
    def fail(request, **kwargs):
        raise HTTPError(request.full_url, 500, "fail", {}, BytesIO(b"server failure"))
    monkeypatch.setattr(pilot, "urlopen", fail)
    payload = {"model": "qwen2.5-coder:7b", "options": {"temperature": 0.0, "top_p": .9,
        "num_predict": 4096, "num_ctx": 32768, "seed": 42}, "format": Bodies.model_json_schema()}
    request = Request("http://localhost:11434/api/generate", data=json.dumps(payload).encode())
    with pytest.raises(HTTPError):
        Ledger(tmp_path, "qwen_base")(request)
    assert (out / "dispatch.json").exists()
    assert (out / "http_error.txt").read_bytes() == b"server failure"


def test_duplicate_keys_rejected():
    from llm_ontology.inference.structured_output import parse_testing_bodies
    with pytest.raises(ValueError, match="Duplicate"):
        parse_testing_bodies('{"testCase1":"x;","testCase1":"z;","testCase2":"y;"}')


def test_wrong_assertions_still_functionally_usable(tmp_path):
    from llm_ontology.benchmarks.defects4j_bodies_pilot import usable
    path = tmp_path / "predictions/qwen_base/metrics/evaluation.json"
    path.parent.mkdir(parents=True)
    run = {"compile": {"returncode": 0}, "console_summary": {"tests_started": 2},
           "status": "assertion_failure"}
    path.write_text(json.dumps({"outcomes": {"fixed": [run, run]}}))
    assert usable(tmp_path)
    run["console_summary"]["tests_started"] = 0
    path.write_text(json.dumps({"outcomes": {"fixed": [run, run]}}))
    assert not usable(tmp_path)


def test_identical_scaffold_and_contract_across_retrieval_modes():
    from llm_ontology.approaches import RetrievedContext
    from llm_ontology.inference.prompting.canonical import normalize_retrieved_evidence
    c = apply_profile(case())
    contexts = (RetrievedContext(document_id="train-only", content="untrusted example",
        source="testing_db", score=1.0, metadata={"collection": "testing_db"}),)
    prompts = [BodyPromptBuilder().build(task="testing", instruction=c.instruction,
        requirements=c.requirements, input_text=c.input_text, approach=mode,
        contexts=() if mode == "direct" else contexts).text for mode in ("direct", "rag", "multi_rag")]
    assert len({normalize_retrieved_evidence(p) for p in prompts}) == 1
    assert all(scaffold(case()) in p for p in prompts)
