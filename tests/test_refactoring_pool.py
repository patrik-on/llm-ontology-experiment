from __future__ import annotations

from copy import deepcopy
import json

import pytest

from llm_ontology.benchmarks import refactoring_matrix as matrix
from llm_ontology.benchmarks import refactoring_prepare as prep
from llm_ontology.benchmarks.refactoring_pool import behavior_mutants, pool


def test_mutations_touch_changed_methods_only_and_preserve_unicode():
    before = 'class A { String f() { return "ž"; } int g(){return 1;} }'
    gold = 'class A { String f() { return helper(); } String helper(){return "ž";} int g(){return 1;} }'
    mutants = behavior_mutants(before, gold, 8)
    assert len(mutants) == 2
    assert all('int g(){return 1;}' in m["source"] for m in mutants)
    assert all("EVALUATOR_BEHAVIOR_CONTROL" in m["source"] for m in mutants)
    assert len(behavior_mutants(before, gold, 1)) == 1
    focus = 'String helper(){return "ž";}'
    assert len(behavior_mutants(before, gold, 8, focus)) == 1
    assert behavior_mutants(before, before, 8) == []


@pytest.mark.local_data
def test_pool_excludes_flagged_unsupported_and_test_paths():
    plan = matrix.load_plan("all")
    records, _, identity = pool(matrix.REPO, plan)
    assert identity == plan["pool_identity"]
    assert len(records) == len({r["uniqueId"] for r in records})
    assert all(r["projectName"] != "pmd" and r["type"] in {"Extract Method", "Inline Method"}
               and "/test/" not in "/" + r["filePathBefore"]
               and r["filePathBefore"] == r["filePathAfter"] for r in records)


def test_missing_jdk_rejected_before_fetch(monkeypatch):
    monkeypatch.setattr(prep.ex, "acquire", lambda *a: pytest.fail("Fetched before JDK check"))
    record = {"projectName": "example", "type": "Extract Method", "compileJDK": 21,
              "filePathBefore": "A.java", "filePathAfter": "A.java"}
    with pytest.raises(ValueError, match="JDK 21"):
        prep.make_case(record, {}, {"excluded_projects": [], "jdk_homes": {}})


def qa_fakes(monkeypatch, outcomes):
    expected = [["A#t", "passed"]]
    baseline = {"status": "passed", "compiled": True, "test_reports": {"signature": expected}}
    calls = []
    def execute(case, source, out, *args, **kwargs):
        calls.append(str(out))
        return deepcopy(baseline if "baseline-" in str(out) else outcomes[len(calls) - 3])
    def evaluate(case, source, out, *args):
        if out.name == "reference":
            return {"verified_success": True}
        if out.name == "noop":
            return {"status": "no_op"}
        return {"outcomes": [{"status": "compile_failure"}] * 2}
    monkeypatch.setattr(prep.ex, "execute", execute)
    monkeypatch.setattr(prep.ex, "evaluate", evaluate)
    return {"before": "class A {int f(){return 1;}}"}, "class A {int f(){return 2;}}"


@pytest.mark.parametrize("kind", ["killed", "survived", "compile_failure", "changed_tests", "unstable"])
def test_behavior_control_requires_compilation_same_tests_and_stable_failure(tmp_path, monkeypatch, kind):
    result = {"compiled": kind != "compile_failure",
              "status": "test_failure" if kind not in {"survived", "compile_failure"} else kind,
              "test_reports": {"signature": [["B#t" if kind == "changed_tests" else "A#t", "failed"]]}}
    other = deepcopy(result)
    if kind == "unstable":
        other["test_reports"]["signature"] = [["A#t", "passed"]]
    case, gold = qa_fakes(monkeypatch, [result, other])
    outcome = prep.qa(case, gold, None, tmp_path / "qa", {})
    assert outcome["passed"] == (kind == "killed")
    assert (tmp_path / "qa/behavior-0/mutant.java").exists()


@pytest.mark.local_data
def test_prepare_exact_n_blocks_shortfall_and_all_uses_only_qa_passes(tmp_path, monkeypatch):
    plan = matrix.load_plan(6)
    records, overrides, identity = pool(matrix.REPO, plan)
    small = records[:3]
    monkeypatch.setattr(prep, "pool", lambda *a: (small, overrides, identity))
    monkeypatch.setattr(prep, "tool_identity", lambda *a: {})
    monkeypatch.setattr(prep, "make_case", lambda r, *a: {"id": r["uniqueId"]})
    def controls(case, *a):
        return {"passed": case["id"] != small[1]["uniqueId"], "checks": {"control": False},
                "expected_tests": [["A#t", "passed"]]}
    monkeypatch.setattr(prep, "qa", controls)
    def screen(*args):
        return {"base": 1}
    assert not prep.prepare(tmp_path, plan, screen)["ready"]
    assert not (tmp_path / "selection.json").exists()
    plan["cases"] = "all"
    result = prep.prepare(tmp_path, plan, screen)
    assert result["ready"] and result["pool_exhausted"] and result["accepted"] == 2
    assert len(json.loads((tmp_path / "selection.json").read_text())["cases"]) == 2


@pytest.mark.local_data
def test_partial_preparation_is_not_silently_reused(tmp_path, monkeypatch):
    plan = matrix.load_plan(1)
    records, overrides, identity = pool(matrix.REPO, plan)
    monkeypatch.setattr(prep, "pool", lambda *a: (records[:1], overrides, identity))
    monkeypatch.setattr(prep, "tool_identity", lambda *a: {})
    (tmp_path / "preparation" / records[0]["uniqueId"]).mkdir(parents=True)
    with pytest.raises(ValueError, match="Interrupted partial"):
        prep.prepare(tmp_path, plan, lambda *a: {})


@pytest.mark.local_data
def test_all_dry_run_has_upper_bound_no_runtime(tmp_path, monkeypatch, capsys):
    # The CLI changes cwd; register it for teardown before swapping its repo root.
    monkeypatch.chdir(matrix.REPO)
    monkeypatch.setattr(matrix, "REPO", tmp_path)
    monkeypatch.setattr(matrix.shared, "require_wsl", lambda: pytest.fail("Runtime invoked"))
    assert matrix.main(["--run-id", "all-preview", "--cases", "all", "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["maximum_is_upper_bound"] and result["maximum_calls"] == result["pool_size"] * len(matrix.ARMS)
    assert not list(tmp_path.iterdir())


@pytest.mark.local_data
def test_numeric_six_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(matrix.REPO)
    monkeypatch.setattr(matrix, "REPO", tmp_path)
    assert matrix.main(["--run-id", "six-preview", "--cases", "6", "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["maximum_calls"] == 6 * len(matrix.ARMS) and not result["maximum_is_upper_bound"]
    assert not list(tmp_path.iterdir())


@pytest.mark.local_data
def test_all_requires_exhausted_preparation(tmp_path, monkeypatch):
    plan = matrix.load_plan("all")
    ident = plan["pool_identity"]["ids"][0]
    matrix.write(tmp_path / "matrix_plan.json", plan)
    matrix.write(tmp_path / "selection.json", {"cases": [{"id": ident}], "indexing_allowed": False})
    matrix.write(tmp_path / "preparation.json", {"ready": True, "accepted": 1, "pool_exhausted": False})
    with pytest.raises(ValueError, match="Complete audited preparation"):
        matrix.Matrix(tmp_path)


@pytest.mark.local_data
def test_pool_rejects_changed_dataset_hash(monkeypatch):
    plan = matrix.load_plan()
    monkeypatch.setattr(prep.ex, "file_sha256", lambda *a: "changed")
    with pytest.raises(ValueError, match="Dataset differs"):
        pool(matrix.REPO, plan)
