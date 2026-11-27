"""R1 v2 (requested method in input / output), the c2 catalogue and the covered_by check of none."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyshacl")
pytest.importorskip("tree_sitter_java")

from llm_ontology.repair import java_facts as J  # noqa: E402
from llm_ontology.repair import proposal as P  # noqa: E402
from llm_ontology.repair import rules as R  # noqa: E402
from llm_ontology.repair.loop import Loop, d2_schema  # noqa: E402
from llm_ontology.repair.mock import ScriptedProvider, SyntheticRefactoringTask, scripted  # noqa: E402
from llm_ontology.repair.replay import replay, validate  # noqa: E402
from llm_ontology.repair.verify import load_pool  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIX = REPO / "data/repair/mechanism"
D1_V1 = REPO / "configs/repair/rules_d1/refactoring.ttl"
D1_V2 = REPO / "configs/repair/rules_d1/refactoring_v2.ttl"
V1_SHA = "c5940d0459a8c30a791a9753c6a70f8f7057f2a670595ba5c3de03f3e02a8f0f"  # pilot repair-pv-pilot-20261127

BEFORE = """class Calc {
    public int run(int x) {
        int limit = 10;
        if (x > limit) {
            return limit;
        }
        return x;
    }
}
"""
# the request names a method that the input does not have (it has to be extracted)
REQUEST = "Parameterize Variable\tlimit : int to limit : int in method private clamp(x int, limit int) : int from class a.Calc"
NOT_EXTRACTED = BEFORE.replace("return x;", "return x; // unchanged")  # local kept, no clamp
EXTRACTED = """class Calc {
    public int run(int x) {
        int limit = 10;
        return clamp(x, limit);
    }

    private int clamp(int x, int limit) {
        if (x > limit) {
            return limit;
        }
        return x;
    }
}
"""


def graph(after: str, request: str = REQUEST):
    return J.refactoring_graph(BEFORE, after, request, 3)


def r1(after: str, base: dict, request: str = REQUEST) -> list[str]:
    return [r["message"] for r in R.violations(R.findings(graph(after, request), base), "R1")]


def test_v1_base_is_unchanged_and_v2_has_docs():
    assert R.base_hash(R.load_d1("refactoring", D1_V1)) == V1_SHA
    d2 = R.load_d1("refactoring", D1_V2)
    assert set(d2["rule_docs"]) == {"R1", "R2"} and "lo:targetMethodInInput" in d2["facts_vocabulary"]
    assert "requested signature" in P.catalogue(d2)["rules"]["R1"]


def test_facts_and_r1_v2_messages():
    g = graph(NOT_EXTRACTED)
    req = J.LO.request
    assert (req, J.LO.targetMethodInInput, None) in g and not g.value(req, J.LO.targetMethodInInput).toPython()
    assert g.value(req, J.LO.requestedSignature).toPython() == "clamp(int, int)"
    v1, v2 = R.load_d1("refactoring", D1_V1), R.load_d1("refactoring", D1_V2)
    assert any("must keep its name" in m for m in r1(NOT_EXTRACTED, v1))  # the misleading v1 message
    assert r1(NOT_EXTRACTED, v2) == ["R1 the requested method clamp(int, int) was not found in the supplied input, "
                                        "and your output does not declare a method with this signature either."]
    assert r1(EXTRACTED, v2) == []
    assert graph(EXTRACTED).value(req, J.LO.targetSignatureInOutput).toPython() is True
    # the method is in the input but missing in the output: the "keep its name" message stays
    existing = REQUEST.replace("private clamp(x int, limit int)", "public run(x int, limit int)")
    assert r1(BEFORE.replace("run(int x)", "go(int x)"), v2, existing) == [
        "R1 the requested method run(int, int) is declared in the input but was not found in your output "
        "(it must keep its name unless the request renames it)."]


def add(must_hold, **over):
    p = {"decision": "add", "evidence": {"snippet": "int limit = 10;"}, "applies_when": "Parameterize Variable",
         "must_hold": must_hold, "except_when": "none",
         "message": "create {?sig} from the code that uses {?local} (line {?sline} of {?src}) and pass it as a parameter"}
    p.update(over)
    return P.RuleProposal.model_validate(p)


def test_c2_combines_two_conditions_and_needs_both():
    d1 = R.load_d1("refactoring", D1_V2)
    both = ["requested_signature_missing_in_output", "variable_kept_local_in_source_method"]
    new, rid, _ = P.apply(d1, add(both), "t", NOT_EXTRACTED, "c2")
    flagged = lambda answer, base, rule: bool(R.violations(R.findings(graph(answer), base), rule))  # noqa: E731
    assert flagged(NOT_EXTRACTED, new, rid)
    assert not flagged(EXTRACTED, new, rid)  # a correct extraction keeps the local in run(): not flagged
    alone, rid1, _ = P.apply(d1, add(["variable_kept_local_in_source_method"],
                                     message="{?src} still declares {?local}"), "t", EXTRACTED, "c2")
    assert flagged(EXTRACTED, alone, rid1)  # one condition alone would flag the correct answer
    c = next(r for r in new["rules"] if r["id"] == rid)["constraints"][0]
    assert c["required_facts"] == sorted(set(c["required_facts"])) and "lo:targetSignatureInOutput" in c["required_facts"]
    with pytest.raises(R.ProposalError, match="bad_combination"):
        P.apply(d1, add(both + ["target_method_missing_in_input"]), "t", NOT_EXTRACTED, "c2")
    with pytest.raises(R.ProposalError, match="bad_combination"):  # c1 takes one condition as a string
        P.apply(d1, add(["old_local_still_declared"], message="x"), "t", NOT_EXTRACTED, "c1")
    with pytest.raises(R.ProposalError, match="unknown_condition"):  # c2 conditions are not in c1
        P.apply(d1, add("target_method_missing_in_input", message="x {?sig}"), "t", NOT_EXTRACTED, "c1")


def test_prompt_and_schema_per_catalogue():
    d1 = R.load_d1("refactoring", D1_V2)
    c1, c2 = P.schema(d1, "c1"), P.schema(d1, "c2")
    assert c1["anyOf"][0]["properties"]["must_hold"]["type"] == "string"
    assert c2["anyOf"][0]["properties"]["must_hold"]["maxItems"] == 2
    assert sorted(c2["anyOf"][0]["properties"]["must_hold"]["items"]["enum"]) == sorted(P.catalogue(d1, "c2")["conditions"])
    assert c1["anyOf"][2]["properties"]["covered_by"]["properties"]["rule"]["enum"] == ["R1", "R2"]
    t1, t2 = P.prompt_section(d1, "c1"), P.prompt_section(d1, "c2")
    assert "target_method_missing_in_input" in t2 and "target_method_missing_in_input" not in t1
    assert "covered_by" in t1 and "a list of 1 or 2" in t2
    assert d2_schema(d1, "c2")["properties"]["rule_proposal"] == c2


REPORT_R1 = "R1 modifiers of class Calc changed from 'public' to '(none)'. The requested operation does not change modifiers; restore them."
REPORT_R2 = "R2 Parameterize Variable: method run(int) must declare a new parameter 'limit' of type int; your output has parameters (x)."


@pytest.mark.parametrize("proposal, outcome", [
    ({"reason": "R1 already reports the removed modifier", "covered_by": {"rule": "R1", "report": REPORT_R1}}, ""),
    ({"reason": "R1 already reports it", "covered_by": {"rule": "R1", "report": REPORT_R1[:60]}}, ""),  # shortened
    ({"reason": "R1 already reports it", "covered_by": {"rule": "R1", "report": REPORT_R2}}, "covered_rule_mismatch"),
    ({"reason": "R2 already reports it", "covered_by": {"rule": "R2", "report": "R2 something else entirely here"}},
     "covered_report_not_found"),
    ({"reason": "R2 already reports this error"}, "uncited_rule_claim"),
    ({"reason": "R2 reports it", "covered_by": {"rule": "R1", "report": REPORT_R1}}, "uncited_rule_claim"),
    ({"reason": "R2 does not report this; no listed condition expresses it"}, ""),
    ({"reason": "no listed condition expresses the missing method"}, ""),
    ({"reason": "covered", "covered_by": {"rule": "R7", "report": REPORT_R1}}, "unknown_target_rule"),
])
def test_none_must_cite_the_report_it_relies_on(proposal, outcome):
    d1 = R.load_d1("refactoring", D1_V2)
    result = validate({"decision": "none", **proposal}, d1, BEFORE, [REPORT_R1, REPORT_R2])
    assert (result["valid"], result["reason"]) == (not outcome, outcome), result
    if proposal.get("covered_by") and not outcome:
        assert result["covered_by"]["report"] == REPORT_R1


def test_replay_with_new_d1_and_catalogue(tmp_path):
    task = SyntheticRefactoringTask.from_file(FIX / "loop_cases.json")
    v1 = R.load_d1("refactoring", D1_V1)
    pool = load_pool(FIX / "dev_pool.json")
    source = tmp_path / "pilot"
    Loop(source, task, ScriptedProvider(scripted(task.cases(), {})), d1=v1, pool=pool,  # every task on v0
         max_new_tokens=512, analysis_tokens=256).run(task.cases())
    (source / "loop_plan.json").write_text(json.dumps({"cases": [c["id"] for c in task.cases()]}))
    (source / "dev_pool.json").write_bytes((FIX / "dev_pool.json").read_bytes())
    before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    v2 = R.load_d1("refactoring", D1_V2)
    provider = ScriptedProvider(scripted(task.cases(), {}))
    rows = replay(source, tmp_path / "b", task, provider, analysis_tokens=256, catalogue="c2", d1=v2,
                  d1_name="configs/repair/rules_d1/refactoring_v2.ttl", development=True)
    assert {p: p.read_bytes() for p in source.rglob("*") if p.is_file()} == before  # pilot untouched
    plan = json.loads((tmp_path / "b/replay_plan.json").read_text())
    assert plan["catalogue"] == "c2" and plan["rules_d1_sha256"] == R.base_hash(v2) and plan["development_cases"]
    assert all((tmp_path / "b/cases" / r["case"] / "rules.json").exists() for r in rows)
    assert all("target_method_missing_in_input" in p for p in provider.prompts)
    report = (tmp_path / "b/replay_report.md").read_text()
    assert "**vývojové**" in report and "Katalóg: `c2`" in report
