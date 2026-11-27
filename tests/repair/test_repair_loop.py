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

from llm_ontology.repair import rules as R  # noqa: E402
from llm_ontology.repair.loop import Loop  # noqa: E402
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
                          trigger=task.facts(c, c["bad"]), pool=pool)
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
    state.propose(task="a1", group="same", proposal=REFINE, evidence={}, trigger=task.facts(c, c["bad"]), pool=pool)
    assert state.begin_task("a2", "same")[0] == 0  # alternative answer to the same prompt
    assert state.begin_task("b1", "other")[0] == 1


def test_invalid_and_deferred_proposals(tmp_path):
    d1 = R.load_d1("refactoring", D1_REF)
    pool = load_pool(FIX / "dev_pool.json")
    state = RuleState(tmp_path / "d2", d1)
    cases = {
        "u1": ({**REFINE, "template": "free_sparql"}, "rejected", "unknown_template"),
        "u2": ({**REFINE, "message": "uses {?secret}"}, "rejected", "bad_message"),
        "u3": ({**REFINE, "missing_facts": ["lo:callGraph"]}, "deferred", "missing_extraction"),
        "u4": ({"decision": "none"}, "none", ""),
        "u5": ({"decision": "maybe"}, "rejected", "invalid_proposal"),
        "u6": ({**REFINE, "target_rule": "R9"}, "rejected", "unknown_target_rule"),
    }
    for i, (proposal, decision, reason) in cases.items():
        state.begin_task(i, i)
        entry = state.propose(task=i, group=i, proposal=proposal, evidence={}, trigger=None, pool=pool)
        assert (entry["decision"], entry["reason"]) == (decision, reason), i
    assert state.latest == 0


def test_pending_without_heldout_examples(tmp_path):
    d1 = R.load_d1("refactoring", D1_REF)
    only_positive = [e for e in load_pool(FIX / "dev_pool.json") if e.defective]
    state = RuleState(tmp_path / "d2", d1)
    state.begin_task("p1", "p1")
    entry = state.propose(task="p1", group="p1", proposal=REFINE, evidence={}, trigger=None, pool=only_positive)
    assert (entry["decision"], entry["reason"]) == ("pending", "missing_examples")


def test_repeating_an_existing_rule_is_rejected(tmp_path):
    """Testing: a template that restates T3 (incl. the assertThrows exception) adds nothing."""
    d1 = R.load_d1("testing", D1_TEST)
    pool = load_pool(FIX / "dev_pool.json")
    state = RuleState(tmp_path / "d2", d1)
    state.begin_task("t", "t")
    restated = {"decision": "add", "template": "mutated_argument_from_factory", "params": {"mutability": "Immutable"},
                "exception": "inside_expected_exception", "message": "argument {?pos} of {?display} is immutable"}
    from rdflib import Graph
    trigger = Graph().parse(FIX / "testing/defective.ttl")
    entry = state.propose(task="t", group="t", proposal=restated, evidence={}, trigger=trigger, pool=pool)
    assert (entry["decision"], entry["reason"]) == ("rejected", "duplicate_no_added_coverage")
    # without the exception it would also flag the intended assertThrows test
    findings = R.findings(Graph().parse(FIX / "testing/correct.ttl"), R.apply(
        d1, R.RuleProposal.model_validate({**restated, "exception": "none"}), "x")[0])
    assert R.violations(findings, "X1")


def test_analysis_prompts_hide_the_pool(setup):
    task, _, pool, provider, loop = setup
    loop.run(task.cases())
    secret = [e.id for e in pool] + ["pool-scale-a", "manual-synthetic", "v + v + v"]
    for prompt in provider.prompts:
        assert not any(s in prompt for s in secret)
    d2 = [p for p in provider.prompts if p.startswith("You are analysing") and "Templates (closed list)" in p]
    d1 = [p for p in provider.prompts if p.startswith("You are analysing") and "Templates (closed list)" not in p]
    assert len(d2) == 3 and len(d1) == 6
