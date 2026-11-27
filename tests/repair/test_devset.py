"""Development set: first answers in the pilot run layout, then the D2 replay on them."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyshacl")
pytest.importorskip("tree_sitter_java")

from llm_ontology.repair import devset  # noqa: E402
from llm_ontology.repair import rules as R  # noqa: E402
from llm_ontology.repair.mock import ScriptedProvider, SyntheticRefactoringTask, scripted  # noqa: E402
from llm_ontology.repair.replay import replay  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIX = REPO / "data/repair/mechanism"
D1_V2 = REPO / "configs/repair/rules_d1/refactoring.ttl"


def test_requested_method_in_input():
    case = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json").cases()[0]
    assert devset.requested_method_in_input(case)  # run(...) is in the input
    assert not devset.requested_method_in_input({**case, "request": case["request"].replace("run(", "clamp(")})


def test_first_answers_then_replay(tmp_path):
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    d1 = R.load_d1("refactoring", D1_V2)
    root = tmp_path / "devset"
    rows = devset.first_answers(root, task, ScriptedProvider(scripted(task.cases(), {})), repo=REPO, d1=d1,
                                max_new_tokens=512, analysis_tokens=256)
    assert [r["final_success"] for r in rows] == [False, False, False]
    pool = json.loads((root / "dev_pool.json").read_text())
    assert {p["label_source"] for p in pool} == {"final_evaluator", "reference"}
    assert sum(not p["defective"] for p in pool) == 3  # the references
    ledger = [json.loads(x) for x in (root / "rulebase_d2/ledger.jsonl").read_text().splitlines()]
    assert sum(e["type"] == "task_start" for e in ledger) == 3
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    again = devset.first_answers(root, task, ScriptedProvider(lambda p, s: pytest.fail("no new call")), repo=REPO,
                                 d1=d1, max_new_tokens=512, analysis_tokens=256)  # resumes from stored answers
    assert again == rows
    out = replay(root, tmp_path / "replay", task, ScriptedProvider(scripted(task.cases(), {})), analysis_tokens=256,
                 catalogue="c2", development=True)
    assert len(out) == 3 and all(r["format"]["valid"] for r in out)
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file() and p.name != "ledger.jsonl"} == \
        {p: b for p, b in before.items() if p.name != "ledger.jsonl"}
