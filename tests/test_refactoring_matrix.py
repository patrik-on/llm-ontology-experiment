from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from llm_ontology.benchmarks import refactoring_execution as ex
from llm_ontology.benchmarks import refactoring_matrix as matrix
from llm_ontology.benchmarks.refactoring_prepare import tool_identity


@pytest.mark.parametrize("path", ["../A.java", "/A.java", "a/../A.java", "a\\A.java", "C:/A.java", "a//A.java", "./A.java"])
def test_unsafe_paths(path):
    with pytest.raises(ValueError):
        ex.safe_path(path)


@pytest.mark.parametrize("raw", [
    '{"file_path":"A.java","file_path":"B.java","refactored_code":"x"}',
    '{"file_path":"A.java","refactored_code":"x","extra":1}',
    '{"file_path":"B.java","refactored_code":"x"}',
    '{"file_path":"A.java","refactored_code":""}',
    '```json\n{"file_path":"A.java","refactored_code":"x"}\n```',
    '{"file_path":"A.java","refactored_code":12}',
])
def test_exact_contract(raw):
    with pytest.raises(ValueError):
        ex.parse_answer(raw, "A.java")


def test_accept_complete_file():
    assert ex.parse_answer(json.dumps({"file_path": "src/A.java", "refactored_code": "class A {}"}), "src/A.java") == "class A {}"


def test_read_and_parse_preserve_candidate_and_prompt_bytes(tmp_path):
    source = "class A {\r\n}\r\n"
    path = tmp_path / "A.java"
    path.write_bytes(source.encode())
    assert ex.read_utf8(path) == source
    assert ex.parse_answer(json.dumps({"file_path": "A.java", "refactored_code": source}), "A.java") == source


def test_attached_javadoc_and_overload():
    source = "class A {\n/** hello */\npublic int f() { return 1; }\n}"
    assert ex.target_location(source, "f") == {"start": 2, "end": 3, "method": "f"}
    with pytest.raises(ValueError, match="ambiguous"):
        ex.target_location("class A { void f(){} void f(int x){} }", "f")


def test_operation_bound_to_class_path_method_and_overload():
    case = {"operation": "Extract Method", "file_path": "src/A.java", "class_name": "p.A",
            "target": {"method": "f", "start": 4, "end": 8}}
    event = {"type": "Extract Method", "path": "src/A.java", "target_class": "p.A",
             "target_method": "f", "target_start": 4, "target_end": 8}
    assert ex.operation_matches(event, case)
    for key, bad in {"type": "Inline Method", "path": "other/A.java", "target_class": "q.A",
                     "target_method": "g", "target_start": 10, "target_end": 9}.items():
        assert not ex.operation_matches({**event, key: bad}, case)


def xml(root, text):
    p = root / "target/surefire-reports/TEST-A.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_test_report_fails_closed(tmp_path):
    patterns = ["**/target/surefire-reports/TEST-*.xml"]
    assert ex.reports(tmp_path, patterns)["status"] == "no_tests"
    xml(tmp_path, '<testsuite tests="0"/>')
    assert ex.reports(tmp_path, patterns)["status"] == "no_tests"
    xml(tmp_path, '<testsuite tests="1" failures="1"><testcase classname="A" name="t"><failure/></testcase></testsuite>')
    assert ex.reports(tmp_path, patterns)["status"] == "test_failure"
    xml(tmp_path, '<testsuite tests="1"><testcase classname="A" name="t"><failure/></testcase></testsuite>')
    assert ex.reports(tmp_path, patterns)["status"] == "report_error"
    xml(tmp_path, '<testsuite tests="2"><testcase classname="A" name="t"/></testsuite>')
    assert ex.reports(tmp_path, patterns)["status"] == "report_error"
    xml(tmp_path, '<testsuite tests="1" skipped="1"><testcase classname="A" name="t"><skipped/></testcase></testsuite>')
    assert ex.reports(tmp_path, patterns)["status"] == "no_tests"
    xml(tmp_path, '<testsuite tests="1"><testcase classname="A" name="t"/></testsuite>')
    assert ex.reports(tmp_path, patterns)["signature"] == [["A#t", "passed"]]


def test_noop_never_executes(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "execute", lambda *a, **kw: pytest.fail("No-op executed"))
    result = ex.evaluate({"before": "class A {}"}, "class A { /*format*/ }", tmp_path / "check", {})
    assert result["status"] == "no_op" and not result["verified_success"]


def test_test_pass_alone_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "detect", lambda *a: {"status": "operation_missing"})
    monkeypatch.setattr(ex, "execute", lambda *a, **kw: {"status": "passed", "test_reports": {"signature": [["A#t", "passed"]]}})
    result = ex.evaluate({"before": "class A {}"}, "class A {int f(){return 1;}}", tmp_path / "check", {})
    assert not result["verified_success"]


def test_ledger_never_retries_and_checks_prompt(tmp_path):
    prompt, output = tmp_path / "prompt", tmp_path / "out"
    prompt.mkdir()
    output.mkdir()
    (prompt / "prompt.txt").write_text("fixed")
    fake = SimpleNamespace(root=tmp_path, maximum=5, dispatches=lambda: [],
                           prompts=lambda c, a: prompt, out=lambda c, a: output)
    ledger = matrix.Ledger(fake, {"id": "case"}, "qwen_base")
    with pytest.raises(ValueError, match="differs"):
        ledger.charge({"prompt": "changed"})
    assert not (output / "dispatch.json").exists()
    ledger.charge({"prompt": "fixed"})
    with pytest.raises(FileExistsError):
        ledger.charge({"prompt": "fixed"})
    assert ledger.charged


def test_dry_run_no_runtime_or_writes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(matrix.REPO)
    monkeypatch.setattr(matrix, "REPO", tmp_path)
    monkeypatch.setattr(matrix.shared, "require_wsl", lambda: pytest.fail("runtime called"))
    assert matrix.main(["--run-id", "offline-check", "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["maximum_calls"] == 500 and result["model_calls"] == 0
    assert result["cases"] == 100
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("cases", [0, -1, 100000, "bad", "1.5"])
def test_bounded_case_count(cases):
    with pytest.raises(ValueError):
        matrix.load_plan(cases)


def test_expanded_case_count_and_all():
    plan = matrix.load_plan(6)
    assert plan["cases"] == 6 and plan["pool_size"] > 5
    assert plan["pool_size"] == 100
    assert plan["cohort_manifest"]
    assert matrix.load_plan("all")["cases"] == "all"
    assert matrix.load_plan(plan["pool_size"])["cases"] == plan["pool_size"]


def fake_matrix(tmp_path):
    m = object.__new__(matrix.Matrix)
    m.root, m.plan, m.ids, m.maximum = tmp_path, matrix.load_plan(1), ["case"], 5
    m.cases = [{"id": "case", "before": "class A {}", "operation": "Extract Method",
                "class_name": "A", "file_path": "A.java",
                "target": {"method": "f", "start": 2, "end": 4}}]
    m.verify = lambda: None
    for arm in matrix.ARMS:
        p = m.prompts(m.cases[0], arm)
        p.mkdir(parents=True)
        (p / "prompt.txt").write_text("frozen")
    return m


def test_provider_dispatch_contract_and_resume(tmp_path, monkeypatch):
    from llm_ontology.inference.ollama_client import OllamaGenerationResult
    m = fake_matrix(tmp_path)
    count = []
    class Provider:
        def __init__(self, **kwargs):
            self.ledger = kwargs["opener"]
        def resolve_model_digest(self):
            return "digest"
        def generate_result(self, prompt, json_schema):
            self.ledger.charge({"prompt": prompt})
            count.append(1)
            return OllamaGenerationResult(response=json.dumps({"file_path": "A.java", "refactored_code": "class A {int x;}"}),
                model="qwen", model_digest="digest", done=True, done_reason="stop", client_latency_ms=1)
    monkeypatch.setattr(matrix.shared, "OllamaProvider", Provider)
    monkeypatch.setattr(matrix, "runtime", lambda plan: SimpleNamespace(generation_model_digest="digest", generation_timeout_seconds=1800))
    m.generate("qwen_base")
    assert matrix.read(m.out(m.cases[0], "qwen_base") / "completion.json")["status"] == "generated"
    m.generate("qwen_base")
    assert len(count) == 1


def test_report_pending_and_failed_stay_in_denominator(tmp_path):
    m = fake_matrix(tmp_path)
    out = m.out(m.cases[0], "qwen_base")
    matrix.write(out / "dispatch.json", {"charged": True})
    matrix.write(out / "completion.json", {"status": "model_output_failure"})
    report = m.report()
    assert report["actual_calls"] == 1 and not report["complete"]
    assert report["arms"]["qwen_base"]["successes"] == 0
    assert report["arms"]["qwen_base"]["denominator"] == 1
    assert report["paired"]["qwen_base vs skills"]["unresolved"] == 1


def test_ollama_boundary_validates_and_unloads_before_next_backend(tmp_path, monkeypatch):
    from io import BytesIO
    from urllib.request import Request
    import urllib.request
    m = fake_matrix(tmp_path)
    out = m.out(m.cases[0], "qwen_base")
    out.mkdir(parents=True)
    received = []
    def reply(request, **kwargs):
        received.append(json.loads(request.data))
        return BytesIO(b'{"response":"answer"}')
    monkeypatch.setattr(urllib.request, "urlopen", reply)
    ledger = matrix.Ledger(m, m.cases[0], "qwen_base")
    payload = {"prompt": "frozen", "model": "qwen2.5-coder:7b", "stream": False,
        "format": ex.FileAnswer.model_json_schema(), "options": {"temperature": 0, "top_p": .9,
        "num_predict": m.plan["max_new_tokens"], "num_ctx": 32768, "seed": 42}}
    request = Request("http://localhost:11434/api/generate", data=json.dumps(payload).encode())
    assert ledger(request).read() == b'{"response":"answer"}'
    assert received[0]["keep_alive"] == 0
    assert (out / "server_response.json").exists()
    assert matrix.read(out / "dispatch.json")["request"] == received[0]


@pytest.mark.parametrize("prefix", ["12dbeafe", "c28eff3"])
def test_real_miner_extract_and_inline_when_installed(tmp_path, prefix):
    plan = matrix.load_plan()
    try:
        tool = tool_identity(plan)
    except ValueError:
        pytest.skip("Optional RefactoringMiner build absent")
    dataset = matrix.REPO / plan["dataset"]
    if not dataset.exists():
        pytest.skip("Local SWE dataset absent")
    record = next(r for r in json.loads(dataset.read_text()) if r["uniqueId"].startswith(prefix))
    before = record["sourceCodeBeforeForWhole"]
    case = {"before": before, "file_path": record["filePathBefore"], "operation": record["type"],
            "class_name": record["classNameBefore"],
            "target": ex.target_location(before, record["methodNameBefore"].split("#")[-1])}
    result = ex.detect(case, record["sourceCodeAfterForWhole"], tmp_path / "detected", tool)
    assert result["status"] == "matched", result
