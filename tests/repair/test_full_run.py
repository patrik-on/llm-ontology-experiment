"""Loop over all matrix operations: request parsing, R1 facts for any operation, repeated answers,
repair temperature and the reused first attempt."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyshacl")
pytest.importorskip("tree_sitter_java")

from llm_ontology.repair import java_facts as J  # noqa: E402
from llm_ontology.repair import rules as R  # noqa: E402
from llm_ontology.repair.loop import Check, Loop, feedback_text  # noqa: E402
from llm_ontology.repair.mock import ScriptedProvider, SyntheticRefactoringTask, scripted  # noqa: E402
from llm_ontology.repair.verify import load_pool  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIX = REPO / "data/repair/mechanism"
D1 = REPO / "configs/repair/rules_d1/refactoring.ttl"

REQUESTS = {
    "Extract Method\tprotected removeNic(vm VirtualMachineProfile<? extends VMInstanceVO>, nic NicVO) : void extracted "
    "from public cleanupNics(vm VirtualMachineProfile<? extends VMInstanceVO>) : void in class a.B":
        ("removeNic", ("VirtualMachineProfile<?extendsVMInstanceVO>", "NicVO"), True, {"removeNic", "cleanupNics"}),
    "Rename Method\tpublic getSessionId() : long renamed to public getEpoch() : long in class a.B":
        ("getEpoch", (), True, {"getSessionId", "getEpoch"}),
    "Rename Class\tcom.x.HdfsStatsRecorder renamed to com.x.StatsRecorder":
        (None, (), True, {"HdfsStatsRecorder", "StatsRecorder"}),
    "Remove Parameter\tanalysis : boolean in method private reg(plugins InvocationPlugins, analysis boolean) : void "
    "from class a.B": ("reg", ("InvocationPlugins", "boolean"), False, {"reg"}),
    "Rename Parameter\turl : String to uri : URI in method public setUri(uri URI) : void from class a.B":
        ("setUri", ("URI",), True, {"setUri"}),
    "Extract Variable\tkey : String in method public get(realm String, host String) : Credentials from class a.B"
    "\nExtract exactly this original expression: realm + host": ("get", ("String", "String"), True, {"get"}),
}


@pytest.mark.parametrize("text", list(REQUESTS))
def test_parse_any_request(text):
    req = J.parse_any_request(text)
    method, types, after, names = REQUESTS[text]
    assert (req.method, req.param_types, req.signature_after, set(req.names)) == (method, types, after, names)


BEFORE = """public class A {
    private int n;
    public int getSessionId() {
        return n;
    }
    public int other() {
        return 1;
    }
}
"""


def test_r1_for_other_operations():
    d1 = R.load_d1("refactoring", D1)
    request = "Rename Method\tpublic getSessionId() : int renamed to public getEpoch() : int in class a.A"
    renamed = BEFORE.replace("getSessionId", "getEpoch")
    msgs = lambda after: [r["message"] for r in R.violations(R.findings(  # noqa: E731
        J.refactoring_graph(BEFORE, after, request, 4), d1))]
    assert msgs(renamed) == []  # the renamed method is outside the scope check
    assert any("modifiers of class A" in m for m in msgs(renamed.replace("public class", "class")))
    assert any("method other()" in m for m in msgs(renamed.replace("    public int other() {\n        return 1;\n    }\n", "")))
    assert any("requested method getEpoch()" in m for m in msgs(BEFORE))  # nothing renamed


def test_feedback_marks_a_repeated_answer_in_both_styles():
    check = Check("OPERATION_MISSING", False, True, "tool", ["Requested: X"], "class A {}")
    for style in ("repair-feedback-v1", "repair-feedback-v2"):
        text = feedback_text(2, "{}", check, ["R1 x"], None, "D1", 1, style)
        assert "identical to attempt 1" in text and "R1 x" in text
    v2 = feedback_text(1, "RAW", check, None, None, None, None, "repair-feedback-v2")
    assert v2.index("was rejected") < v2.index("RAW") and "Keep everything else unchanged" not in v2


def test_repair_temperature_and_repeat_record(tmp_path):
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    temps = []

    class Recorder(ScriptedProvider):
        def generate(self, prompt, schema, max_tokens, temperature=0.0):
            temps.append((prompt.startswith("You are analysing"), temperature))
            return super().generate(prompt, schema, max_tokens)

    loop = Loop(tmp_path / "run", task, Recorder(scripted(task.cases(), {})), d1=R.load_d1("refactoring", D1),
                pool=load_pool(FIX / "dev_pool.json"), max_new_tokens=512, analysis_tokens=256, variants=("C",),
                repair_temperature=0.7)
    loop.run(task.cases()[:1])
    gens = [t for analysis, t in temps if not analysis]
    assert gens[0] == 0.0 and set(gens[1:]) == {0.7}  # attempt 1 greedy, repairs sampled
    assert {t for analysis, t in temps if analysis} == {0.0}
    completion = json.loads((tmp_path / "run/cases/loop-1/C/completion.json").read_text())
    assert completion["attempts"][1]["repeats_attempt"] == 1  # the scripted model repeats its bad answer
    assert "Attempt 2 is identical to attempt 1" in (tmp_path / "run/cases/loop-1/C/attempt-3/feedback.txt").read_text()


def test_reused_first_attempt(tmp_path):
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    case = task.cases()[0]
    src = tmp_path / "matrix/cases" / case["id"] / "predictions/onto_project"
    src.mkdir(parents=True)
    raw = json.dumps({"file_path": case["file_path"], "refactored_code": case["bad"]})
    (src / "raw.txt").write_text(raw)
    (src / "dispatch.json").write_text(json.dumps({"request": {"prompt": task.prompt(case), "options": {}}}))
    calls = []

    class Counting(ScriptedProvider):
        def generate(self, prompt, schema, max_tokens, temperature=0.0):
            calls.append(prompt)
            return super().generate(prompt, schema, max_tokens)

    loop = Loop(tmp_path / "run", task, Counting(scripted(task.cases(), {})), d1=R.load_d1("refactoring", D1),
                pool=[], max_new_tokens=512, analysis_tokens=256, variants=("C",),
                first_attempt_from=tmp_path / "matrix")
    loop.run([case])
    assert (tmp_path / "run/cases/loop-1/shared/attempt-1/raw.txt").read_text() == raw
    assert task.prompt(case) not in calls  # attempt 1 was not generated again
    (src / "dispatch.json").write_text(json.dumps({"request": {"prompt": "other", "options": {}}}))
    with pytest.raises(ValueError, match="differs from the matrix"):
        Loop(tmp_path / "run2", task, Counting(scripted(task.cases(), {})), d1=R.load_d1("refactoring", D1),
             pool=[], max_new_tokens=512, analysis_tokens=256, variants=("C",),
             first_attempt_from=tmp_path / "matrix").run([case])
