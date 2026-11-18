"""Matrix contract tests: no real model, network, GPU or production index writes."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm_ontology.benchmarks import testing_matrix as matrix
from llm_ontology.benchmarks import methods2test_execution as offline
from llm_ontology.benchmarks.methods2test_statistics import aggregate


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.chdir(matrix.REPO)
    root = tmp_path / "run"
    matrix.write(root / "matrix_plan.json", matrix.load_plan(2))
    matrix.write(root / "selection.json", {"ids": ["one", "two"],
        "cases": [{"id": "one"}, {"id": "two"}],
        "indexing_allowed": False, "split": "official eval"})
    matrix.write(root / "hf_identity.json", {})
    matrix.write(root / "context/identity.json", {"sha256": "skill"})
    (root / "context/SKILL.md").write_text("Existing testing process guidance.")
    matrix.write(root / "leakage_audit.json", {})
    for ident in ["one", "two"]:
        case = root / "cases" / ident
        matrix.write(case / "case.json", {"case_id": ident, "instruction": "Generate tests",
            "input_text": "public class Number { public static int f(int n){return n+1;} }",
            "requirements": "Return JSON bodies only.", "project_context": "API context"})
        (case / "scaffold.java").write_text("scaffold")
        for arm in matrix.ARMS:
            prompt = case / "frozen_prompts" / arm / "prompt.txt"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("frozen " + ident + "/" + arm)
    monkeypatch.setattr(matrix.batch, "runtime", lambda: SimpleNamespace())
    return matrix.Matrix(root)


def fake_direct(c, case, out, ledger, **kwargs):
    ledger.charge({"prompt": (ledger.root / "cases" / case.case_id /
        "frozen_prompts" / ledger.arm / "prompt.txt").read_text()})
    (out / "raw.txt").write_text('{"testCase1":"assertTrue(true);","testCase2":"assertTrue(true);"}')
    return {}


def test_plan_and_skill_are_existing_inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(matrix.REPO)
    default = matrix.load_plan()
    assert default["cases"] == 5 and default["max_actual_generation_calls"] == 25
    plan = matrix.load_plan(7)
    assert plan["max_actual_generation_calls"] == 35
    assert plan["arms"] == list(matrix.ARMS)
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"# Workflow\r\nExisting process\r\n")
    resolved, content = matrix.resolve_skill(path)
    assert resolved == path and content.encode() == path.read_bytes()
    with pytest.raises(ValueError):
        matrix.load_plan(0)


def test_skill_variant_changes_only_instruction(prepared):
    base, skills = prepared.case("one", "qwen_base"), prepared.case("one", "skills")
    assert base.model_dump(exclude={"instruction"}) == skills.model_dump(exclude={"instruction"})
    assert skills.instruction.startswith(base.instruction)
    assert "Existing testing process guidance." in skills.instruction
    assert "Existing testing process guidance." not in matrix.direct_prompt(base)
    assert "Existing testing process guidance." in matrix.direct_prompt(skills)


@pytest.mark.parametrize("bad", ["../escape", ".", "x/y", "x\\y"])
def test_unsafe_or_incomplete_cohort_rejected(prepared, bad):
    selection = matrix.read(prepared.root / "selection.json")
    selection["ids"][0] = bad
    matrix.write(prepared.root / "selection.json", selection)
    with pytest.raises(ValueError):
        matrix.Matrix(prepared.root)


def test_ledger_prompt_identity_and_exclusive_charges(prepared):
    ledger = matrix.Ledger(prepared, "one", "skills")
    with pytest.raises(ValueError, match="frozen"):
        ledger.charge({"prompt": "modified"})
    ledger.charge({"prompt": "frozen one/skills"})
    with pytest.raises(FileExistsError):
        ledger.charge({"prompt": "frozen one/skills"})
    assert len(prepared.dispatches()) == 1
    assert ledger.dispatch_time is not None


def test_successful_and_failed_cells_are_not_retried(prepared, monkeypatch):
    monkeypatch.setattr(matrix.batch, "_generate_direct", fake_direct)
    monkeypatch.setattr(matrix.batch, "assemble", lambda *a: "class GeneratedBodyTests {}")
    prepared.generate("skills")
    prepared.generate("skills")
    assert len(prepared.dispatches()) == 2
    assert all(matrix.read(prepared.out(i, "skills") / "completion.json")["status"] == "assembled"
               for i in prepared.ids)


def test_empty_transport_fail_stops_only_affected_arm(prepared, monkeypatch):
    def empty(c, case, out, ledger, **kwargs):
        fake_direct(c, case, out, ledger)
        (out / "raw.txt").write_text("")
        raise RuntimeError("empty response")
    monkeypatch.setattr(matrix.batch, "_generate_direct", empty)
    prepared.generate("skills")
    assert len(prepared.dispatches()) == 1
    assert (prepared.root / "skills-stop.json").exists()
    assert not (prepared.root / "qwen_base-stop.json").exists()
    assert not (prepared.out("two", "skills") / "dispatch.json").exists()


def test_interrupted_charged_cell_is_never_retried(prepared, monkeypatch):
    matrix.Ledger(prepared, "one", "skills").charge({"prompt": "frozen one/skills"})
    monkeypatch.setattr(matrix.batch, "_generate_direct", lambda *a, **kw: pytest.fail("retry"))
    prepared.generate("skills")
    assert len(prepared.dispatches()) == 1
    assert prepared.progress()["cells"]["one/skills"] == "interrupted_unresolved"


def test_invalid_output_counts_as_failed_attempt_not_arm_stop(prepared, monkeypatch):
    def invalid(c, case, out, ledger, **kwargs):
        fake_direct(c, case, out, ledger)
        (out / "raw.txt").write_text("not JSON")
        raise ValueError("invalid JSON")
    monkeypatch.setattr(matrix.batch, "_generate_direct", invalid)
    prepared.generate("skills")
    report = aggregate(prepared.root, arms=matrix.ARMS)
    assert report["arms"]["skills"]["class_pass"]["denominator"] == 2
    assert report["arms"]["skills"]["class_pass"]["count"] == 0
    assert report["arms"]["qwen_base"]["unattempted_cases"] == 2
    assert len(report["paired_comparisons"]) == 10
    assert not (prepared.root / "skills-stop.json").exists()


def test_new_skill_arm_is_reviewed_before_execution(prepared, monkeypatch):
    out = prepared.out("one", "skills")
    matrix.write(out / "generation.json", {"source_sha256": matrix.batch.sha("class T {void t(){System.exit(0);}}")})
    (out / "generated.java").write_text("class T {void t(){System.exit(0);}}")
    assert offline.review(prepared.root, arms=matrix.ARMS) == {}
    assert matrix.read(out / "metrics.json")["statuses"] == ["source_review_rejected"]


def test_dry_run_has_no_files_or_model_calls(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(matrix.REPO)
    monkeypatch.setattr(matrix, "REPO", tmp_path)
    monkeypatch.setattr(matrix, "CONFIG", Path(__file__).resolve().parents[1] / matrix.CONFIG)
    skill = tmp_path / "SKILL.md"
    skill.write_text("process guidance")
    assert matrix.main(["--run-id", "plan-only", "--cases", "1", "--skill-file", str(skill), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["max_actual_generation_calls"] == 5
    assert not (tmp_path / "artifacts").exists()
