"""Mechanism checks of the C/D1/D2 repair loop with a scripted model (no Ollama, no Java).

Hand-prepared scenario, not model results: task 1 gets an invalid D2 proposal (rejected),
task 2 a valid refinement of R2 (accepted), task 3 is the next distinct task where the
accepted rule changes the feedback and the repair succeeds only in D2.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyshacl")
pytest.importorskip("tree_sitter_java")

from llm_ontology.repair import proposal as P  # noqa: E402
from llm_ontology.repair import rules as R  # noqa: E402
from llm_ontology.repair.loop import Loop, d2_schema  # noqa: E402
from llm_ontology.repair.mock import (NO_EXCEPTION, REFINE, SCENARIO, ScriptedProvider,  # noqa: E402
                                      SyntheticRefactoringTask, scripted)
from llm_ontology.repair.state import RuleState  # noqa: E402
from llm_ontology.repair.verify import load_pool  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIX = REPO / "data/repair/mechanism"
D1_REF = REPO / "configs/repair/rules_d1/refactoring.ttl"
D1_TEST = REPO / "configs/repair/rules_d1/testing.ttl"
@pytest.fixture
def setup(tmp_path):
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    d1 = R.load_d1("refactoring", D1_REF)
    pool = load_pool(FIX / "dev_pool.json")
    provider = ScriptedProvider(scripted(task.cases(), SCENARIO))
    loop = Loop(tmp_path / "run", task, provider, d1=d1, pool=pool, max_new_tokens=512, analysis_tokens=256)
    return task, d1, pool, provider, loop


def test_reject_accept_and_use_on_next_task(setup):
    task, d1, _, provider, loop = setup
    d1_hash = R.base_hash(d1)
    loop.run(task.cases())
    ledger = loop.state.proposals
    assert ledger["loop-1"]["decision"] == "rejected"
    assert ledger["loop-1"]["reason"] == "flags_correct_example"
    assert "pool-logging-helper" in ledger["loop-1"]["checks"]["new_false_positives"]
    assert ledger["loop-2"]["decision"] == "accepted" and ledger["loop-2"]["version"] == 1
    assert ledger["loop-2"]["checks"]["added_coverage"] == ["pool-scale-logonly"]
    assert ledger["loop-2"]["checks"]["regressions"] == []
    # loop-2 itself is repaired with the version it started with (v0) ...
    assert loop.state.tasks["loop-2"]["version"] == 0
    # ... and the change is used from the next distinct task on
    assert loop.state.tasks["loop-3"]["version"] == 1
    root = loop.root / "cases"
    d2_feedback = (root / "loop-3/D2/attempt-2/feedback.txt").read_text()
    d1_feedback = (root / "loop-3/D1/attempt-2/feedback.txt").read_text()
    assert "only for logging" in d2_feedback and "only for logging" not in d1_feedback
    assert "Rule checks" not in (root / "loop-3/C/attempt-2/feedback.txt").read_text()
    table = loop.score(task.cases())
    assert table["loop-3"]["D2"] == {"S@1": False, "S@2": True, "S@3": True, "status": "passed", "calls": 2}
    assert table["loop-3"]["D1"]["S@3"] is False and table["loop-3"]["C"]["S@3"] is False
    assert R.base_hash(d1) == d1_hash  # D1 unchanged
    # attempt 1 generated once per task and shared by the three variants
    calls = [json.loads(line) for line in (loop.root / "calls.jsonl").read_text().splitlines()]
    assert sum(c["variant"] == "shared" for c in calls) == 3
    assert sum(c["kind"] == "analysis" for c in calls) == 9  # one per variant and task


def test_resume_counts_each_change_once(setup):
    task, _, _, provider, loop = setup
    loop.run(task.cases()[:2])
    (loop.root / "cases/loop-2/D2/completion.json").unlink()  # simulated crash after the proposal
    calls_before = (loop.root / "calls.jsonl").read_text()
    again = Loop(loop.root, task, provider, d1=loop.d1, pool=loop.pool, max_new_tokens=512, analysis_tokens=256)
    again.run(task.cases()[:2])
    assert (loop.root / "calls.jsonl").read_text() == calls_before  # stored responses reused
    entries = [json.loads(x) for x in (loop.root / "rulebase_d2/ledger.jsonl").read_text().splitlines()]
    assert sum(e["type"] == "proposal" and e["task"] == "loop-2" for e in entries) == 1
    assert again.state.latest == 1


def test_freeze_stops_d2(tmp_path):
    d1 = R.load_d1("refactoring", D1_REF)
    pool = load_pool(FIX / "dev_pool.json")
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    state = RuleState(tmp_path / "d2", d1)
    c = task.cases()[1]
    state.begin_task("t1", "g1")
    entry = state.propose(task="t1", group="g1", proposal=REFINE, evidence={},
                          trigger=task.facts(c, c["bad"]), pool=pool, answer=c["bad"])
    assert entry["decision"] == "accepted"
    frozen = state.freeze()
    assert frozen["version"] == 1
    number, _ = state.begin_task("t2", "g2")
    assert number == 1
    late = state.propose(task="t2", group="g2", proposal=NO_EXCEPTION, evidence={}, trigger=None, pool=pool)
    assert late["decision"] == "rejected" and late["reason"] == "frozen"
    assert RuleState(tmp_path / "d2", d1).begin_task("t3", "g3")[0] == 1  # also after reload
    assert len(list((tmp_path / "d2/versions").glob("v*.json"))) == 2


def test_activation_waits_for_a_different_group(tmp_path):
    d1 = R.load_d1("refactoring", D1_REF)
    pool = load_pool(FIX / "dev_pool.json")
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    c = task.cases()[1]
    state = RuleState(tmp_path / "d2", d1)
    state.begin_task("a1", "same")
    state.propose(task="a1", group="same", proposal=REFINE, evidence={}, trigger=task.facts(c, c["bad"]), pool=pool,
                  answer=c["bad"])
    assert state.begin_task("a2", "same")[0] == 0  # alternative answer to the same prompt
    assert state.begin_task("b1", "other")[0] == 1


def test_invalid_and_deferred_proposals(tmp_path):
    d1 = R.load_d1("refactoring", D1_REF)
    pool = load_pool(FIX / "dev_pool.json")
    answer = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json").cases()[1]["bad"]
    state = RuleState(tmp_path / "d2", d1)
    cases = {
        "u1": ({**REFINE, "must_hold": "free_sparql"}, "rejected", "unknown_condition"),
        "u2": ({**REFINE, "message": "uses {?secret}"}, "rejected", "bad_message"),
        "u3": ({"decision": "none", "covered_by": {"rule": "none", "report": ""}, "reason": "needs a call graph", "missing_facts": ["lo:callGraph"]},
               "deferred", "missing_extraction"),
        "u4": ({"decision": "none", "covered_by": {"rule": "none", "report": ""}, "reason": "R1 already reports it"}, "rejected", "uncited_rule_claim"),
        "u4b": ({"decision": "none", "covered_by": {"rule": "none", "report": ""}, "reason": "no listed condition expresses this error"}, "none", ""),
        "u4c": ({"decision": "none", "reason": "no listed condition expresses this error"}, "rejected", "missing_covered_by"),
        "u5": ({"decision": "modify", "reason": "x"}, "rejected", "invalid_proposal"),
        "u6": ({**REFINE, "target_rule": "R2_ParameterizeVariable"}, "rejected", "unknown_target_rule"),
        "u7": ({**REFINE, "evidence": {"line": 4, "snippet": 'log.warn("rate is " + rate);'}},
               "rejected", "evidence_not_found"),
        "u8": ({**REFINE, "evidence": {"line": 5, "snippet": "return amount + amount / 5;"}},
               "rejected", "evidence_not_a_logging_use"),
        "u9": ({**REFINE, "except_when": "inside_expected_exception"}, "rejected", "unknown_exception"),
        "u10": ({k: v for k, v in REFINE.items() if k != "target_rule"}, "rejected", "missing_fields"),
        "u11": ({**REFINE, "applies_when": "testing"}, "rejected", "wrong_operation"),
    }
    for i, (proposal, decision, reason) in cases.items():
        state.begin_task(i, i)
        entry = state.propose(task=i, group=i, proposal=proposal, evidence={}, trigger=None, pool=pool, answer=answer)
        assert (entry["decision"], entry["reason"]) == (decision, reason), i
    assert state.latest == 0


def test_add_and_revise_build_shacl_in_code(tmp_path):
    """add creates a new rule, revise extends R2; required_facts and SHACL come from the catalogue."""
    d1 = R.load_d1("refactoring", D1_REF)
    case = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json").cases()[0]
    added, rid, found = P.apply(d1, P.RuleProposal.model_validate(NO_EXCEPTION), "t", case["bad"])
    assert rid == "X1" and found["snippet_lines"] == [4] and found["line_matches"] is True
    constraint = added["rules"][-1]["constraints"][0]
    assert constraint["required_facts"] == R.TEMPLATES["new_parameter_used_only_in_role"]["facts"]
    assert "los:X1_t0 a sh:NodeShape" in R.render(added)
    revised, rid, _ = P.apply(d1, P.RuleProposal.model_validate(
        {**REFINE, "evidence": NO_EXCEPTION["evidence"]}), "t", case["bad"])
    assert rid == "R2" and [c["kind"] for c in revised["rules"][1]["constraints"]] == ["handwritten", "template"]
    assert "los:R2_t1 a sh:NodeShape" in R.render(revised)
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    rows = R.violations(R.findings(task.facts(case, case["bad"]), revised), "R2")
    assert any("only for logging" in r["message"] for r in rows)
    # the snippet may also be copied from the JSON form of the answer
    escaped = {**NO_EXCEPTION, "evidence": {"snippet": 'log.debug(\\"limit=\\" + limit);'}}
    assert P.apply(d1, P.RuleProposal.model_validate(escaped), "t", case["bad"])[1] == "X1"


def test_prompt_and_schema_list_exactly_the_accepted_values():
    d1 = R.load_d1("refactoring", D1_REF)
    cat = P.catalogue(d1)
    schema = P.schema(d1)
    add, revise, none = schema["anyOf"]
    assert sorted(add["properties"]["must_hold"]["enum"]) == sorted(cat["conditions"])
    assert revise["properties"]["target_rule"]["enum"] == ["R1", "R2"]
    assert none["required"] == ["decision", "covered_by", "reason"]
    assert none["properties"]["covered_by"]["properties"]["rule"]["enum"] == ["R1", "R2", "none"]
    text = P.prompt_section(d1)
    for value in [*cat["conditions"], *cat["exceptions"], *cat["rules"], *cat["relations"]]:
        assert value in text
    assert '"decision": "none"' in text and "R1 already reports" in text
    case = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json").cases()[0]
    for cid, cond in cat["conditions"].items():  # every listed combination is accepted
        for exc in cond["exceptions"]:
            snippet = 'log.debug("limit=" + limit);'
            p = P.RuleProposal.model_validate({"decision": "add", "evidence": {"snippet": snippet},
                                               "applies_when": cond["operation"], "must_hold": cid,
                                               "except_when": exc, "message": "check {?m}"})
            P.to_constraint(p, d1, case["bad"])
    loop_schema = d2_schema(d1)
    assert loop_schema["properties"]["rule_proposal"] == schema


def test_pending_without_heldout_examples(tmp_path):
    d1 = R.load_d1("refactoring", D1_REF)
    only_positive = [e for e in load_pool(FIX / "dev_pool.json") if e.defective]
    state = RuleState(tmp_path / "d2", d1)
    state.begin_task("p1", "p1")
    answer = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json").cases()[1]["bad"]
    entry = state.propose(task="p1", group="p1", proposal=REFINE, evidence={}, trigger=None, pool=only_positive,
                          answer=answer)
    assert (entry["decision"], entry["reason"]) == ("pending", "missing_examples")


def test_repeating_an_existing_rule_is_rejected(tmp_path):
    """Testing: a template that restates T3 (incl. the assertThrows exception) adds nothing."""
    d1 = R.load_d1("testing", D1_TEST)
    pool = load_pool(FIX / "dev_pool.json")
    state = RuleState(tmp_path / "d2", d1)
    state.begin_task("t", "t")
    answer = 'foo.merge(List.of("a"));'
    restated = {"decision": "add", "evidence": {"snippet": 'foo.merge(List.of("a"))'}, "applies_when": "testing",
                "must_hold": "mutated_argument_from_factory:Immutable", "except_when": "inside_expected_exception",
                "message": "argument {?pos} of {?display} is immutable"}
    from rdflib import Graph
    trigger = Graph().parse(FIX / "testing/defective.ttl")
    entry = state.propose(task="t", group="t", proposal=restated, evidence={}, trigger=trigger, pool=pool,
                          answer=answer)
    assert (entry["decision"], entry["reason"]) == ("rejected", "duplicate_no_added_coverage")
    # without the exception it would also flag the intended assertThrows test
    findings = R.findings(Graph().parse(FIX / "testing/correct.ttl"), P.apply(
        d1, P.RuleProposal.model_validate({**restated, "except_when": "none"}), "x", answer)[0])
    assert R.violations(findings, "X1")


def test_analysis_prompts_hide_the_pool(setup):
    task, _, pool, provider, loop = setup
    loop.run(task.cases())
    secret = [e.id for e in pool] + ["pool-scale-a", "manual-synthetic", "v + v + v"]
    for prompt in provider.prompts:
        assert not any(s in prompt for s in secret)
    d2 = [p for p in provider.prompts if p.startswith("You are analysing") and "### Rule proposal" in p]
    d1 = [p for p in provider.prompts if p.startswith("You are analysing") and "### Rule proposal" not in p]
    assert len(d2) == 3 and len(d1) == 6


def test_replay_keeps_the_source_run(setup, tmp_path):
    from llm_ontology.repair.replay import replay

    task, _, _, provider, loop = setup
    loop.run(task.cases())
    before = {p: p.read_bytes() for p in loop.root.rglob("*") if p.is_file()}
    proposals = {"loop-1": {"decision": "none", "covered_by": {"rule": "none", "report": ""}, "reason": "R2 cannot see it"},
                 "loop-2": REFINE,
                 "loop-3": {**NO_EXCEPTION, "evidence": {"snippet": "not in the answer"}}}
    replayer = ScriptedProvider(scripted(task.cases(), proposals))
    (loop.root / "loop_plan.json").write_text(json.dumps({"cases": [c["id"] for c in task.cases()]}))
    (loop.root / "dev_pool.json").write_bytes((FIX / "dev_pool.json").read_bytes())
    before[loop.root / "loop_plan.json"] = (loop.root / "loop_plan.json").read_bytes()
    before[loop.root / "dev_pool.json"] = (loop.root / "dev_pool.json").read_bytes()
    rows = replay(loop.root, tmp_path / "replay", task, replayer, analysis_tokens=256)
    assert {p: p.read_bytes() for p in loop.root.rglob("*") if p.is_file()} == before
    by = {r["case"]: r for r in rows}
    assert by["loop-1"]["format"] == {"valid": True, "reason": "", "decision": "none", "covered_by": None}
    assert by["loop-2"]["format"]["valid"] and by["loop-2"]["verification_info"]["decision"] == "accepted"
    assert by["loop-3"]["format"]["reason"] == "evidence_not_found"
    assert by["loop-2"]["original"]["decision"] == "accepted"
    report = (tmp_path / "replay" / "replay_report.md").read_text()
    assert "| Formálne platný výstup | 2/3 |" in report and "neoverené" in report
    assert len(replayer.prompts) == 3
