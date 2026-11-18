from copy import deepcopy
import json

import pytest

from llm_ontology.benchmarks import refactoring_cohort as cohort
from llm_ontology.benchmarks import refactoring_matrix as matrix
from llm_ontology.benchmarks import refactoring_structural as structural
from llm_ontology.datasets.ml4refactoring import extract_refactoring_type


@pytest.mark.parametrize("name", ["Extract And Move Method", "Move And Rename Class", "Extract Variable",
                                  "Inline Variable", "Rename Parameter", "Parameterize Variable",
                                  "Replace Variable With Attribute"])
def test_raw_type_not_unknown_or_simple_substring(name):
    assert extract_refactoring_type("Foo.java-1-" + name + "-0-") == name


def test_stratified_selection_same_members_independent_of_input_order():
    cases = [{"id": str(i), "source": source, "operation": op} for i, (source, op) in enumerate([
        ("swe", "Extract Method"), ("marv", "Rename Variable"), ("marv", "Rename Variable"),
        ("ml4refactoring", "Rename Class"), ("ml4refactoring", "Rename Class")])]
    assert cohort.subset(cases, 3) == cohort.subset(list(reversed(cases)), 3)
    assert len({c["source"] for c in cohort.subset(cases, 3)}) == 3
    assert len(cohort.subset(cases, "all", source="marv")) == 2
    with pytest.raises(ValueError, match="only 2"):
        cohort.subset(cases, 3, source="marv")


def test_absent_or_short_cohort_fails_closed(tmp_path):
    plan = {"cohort_manifest": "manifest.json"}
    with pytest.raises(ValueError, match="not released"):
        cohort.load(tmp_path, plan)
    (tmp_path / "manifest.json").write_text(json.dumps({"cases": []}))
    with pytest.raises(ValueError, match="100"):
        cohort.load(tmp_path, plan)


def test_legacy_purity_diagnostic_is_not_the_target_only_endpoint():
    event = {"type": "Rename Variable", "left": [{"codeElement": "old : int"}],
             "right": [{"codeElement": "newName : int"}]}
    before = 'class A {int f(){int old=1;return old;} String s="old";}'
    after = 'class A {int f(){int newName=1;return newName;} String s="old";}'
    for side, text in (("left", before), ("right", after)):
        event[side][0].update(startLine=1, endLine=1, startColumn=1, endColumn=len(text)+1)
    assert structural.within_scope(before, after, event)
    assert not structural.within_scope(before, after.replace("=1", "=2"), event)
    assert not structural.within_scope(before, after.replace('"old"', '"newName"'), event)


def test_valid_java_requires_compilation_unit_not_diff_or_method_snippet():
    assert structural.valid_java("package p; class A {}")
    assert not structural.valid_java("@@ -1,2 +1,2 @@")
    assert not structural.valid_java("void f() {}")


def test_structural_instructions_express_target_without_gold_body():
    case = {"evaluation_level": "structural", "operation": "Rename Parameter", "request": "Rename x to count in A.f",
            "target": {"start": 2, "end": 3}, "file_path": "A.java"}
    inst = matrix.instruction(case)
    assert "Rename x to count" in inst and "A.java" in inst and "2..3" in inst


def test_real_miner_target_binding_scope_and_noop(tmp_path):
    from llm_ontology.benchmarks.refactoring_prepare import tool_identity
    tool = tool_identity(matrix.load_plan(1))
    before = "class A { int f(int old) { return old; } int g(int old) { return old; } }"
    after = "class A { int f(int count) { return count; } int g(int old) { return old; } }"
    base = {"file_path": "A.java", "before": before, "class_name": "A", "operation": "Rename Parameter",
            "target": {"method": "f", "start": 1, "end": 1}}
    events = matrix.ex.detect(base, after, tmp_path / "detect", tool)["events"]
    event = structural.select_event(events, "Rename Parameter", before, after)
    case = {**base, "target_event": structural.identity(event)}
    result = structural.evaluate(case, after, tmp_path / "reference", tool)
    assert result["structural_success"] and not result["verified_success"]
    assert result["behavioral_validation"] == "not_run"
    assert structural.evaluate(case, before, tmp_path / "noop", tool)["status"] == "no_op"
    wrong = after.replace("f(int count) { return count; } int g(int old) { return old; }",
                          "f(int old) { return old; } int g(int count) { return count; }")
    assert not structural.evaluate(case, wrong, tmp_path / "wrong", tool)["structural_success"]
    both = after.replace("g(int old) { return old; }", "g(int count) { return count; }")
    assert structural.evaluate(case, both, tmp_path / "two-targets", tool)["structural_success"]
    dirty = after.replace("return count;", "return count + 1;")
    # Target-only structural scoring deliberately does NOT certify behavior.
    assert structural.evaluate(case, dirty, tmp_path / "dirty", tool)["structural_success"]
    fake = deepcopy(case)
    fake["target_event"]["left"][0]["startLine"] += 1
    assert not structural.evaluate(fake, after, tmp_path / "wrong-location", tool)["structural_success"]


def test_report_does_not_mix_structural_success_with_build_tests(tmp_path):
    obj = object.__new__(matrix.Matrix)
    obj.root, obj.plan = tmp_path, matrix.load_plan(1)
    obj.ids, obj.maximum = ["marv-case"], 5
    obj.cases = [{"id": "marv-case", "source": "marv", "operation": "Rename Method",
                  "evaluation_level": "structural"}]
    out = obj.out(obj.cases[0], "qwen_base")
    matrix.write(out / "dispatch.json", {})
    matrix.write(out / "completion.json", {"status": "generated"})
    (out / "generated.java").write_text("class A {}")
    matrix.write(out / "evaluation/evaluation.json", {"status": "structural_pass", "structural_success": True,
        "verified_success": False, "source_sha256": matrix.ex.file_sha256(out / "generated.java")})
    report = obj.report()
    arm = report["arms"]["qwen_base"]
    assert arm["successes"] == 1 and arm["denominator"] == 1
    assert arm["project_verified_successes"] == 0 and arm["build_test_denominator"] == 0
    cell = next(r for r in report["cells"] if r["arm"] == "qwen_base")
    assert cell["compiled"] is None and cell["tests_stable"] is None
    assert not report["complete"]


def test_real_parameterization_includes_necessary_parameter_delimiter(tmp_path):
    from llm_ontology.benchmarks.refactoring_prepare import tool_identity
    tool = tool_identity(matrix.load_plan(1))
    before = "class A {int f(int a) { int value = 1; return a + value; }}"
    after = "class A {int f(int a, int value) { return a + value; }}"
    case = {"before": before, "operation": "Parameterize Variable", "file_path": "A.java", "class_name": "A",
            "target": {"method": "f", "start": 1, "end": 1}}
    events = matrix.ex.detect(case, after, tmp_path / "detector", tool)["events"]
    event = structural.select_event(events, "Parameterize Variable", before, after)
    assert structural.within_scope(before, after, event)


def test_context_aligns_members_and_preserves_reasonable_neighbors(tmp_path):
    from llm_ontology.benchmarks.refactoring_context import contextual_pair
    from llm_ontology.benchmarks.refactoring_prepare import tool_identity
    tool = tool_identity(matrix.load_plan(1))
    before = '''package p;
class A {
 int state = 1;
 int farBefore(){return -1;}
 int neighborBefore(){return 0;}
 int focus(int old){return old + state;}
 int neighborAfter(){return 2;}
 int farAfter(){return 3;}
}'''
    after = before.replace("int old", "int count").replace("return old +", "return count +").replace("return 3;", "return 99;")
    base = {"file_path": "A.java", "before": before, "operation": "Rename Parameter", "class_name": "p.A",
            "target": {"method": "focus", "start": 6, "end": 6}}
    event = structural.select_event(matrix.ex.detect(base, after, tmp_path / "full", tool)["events"], "Rename Parameter")
    left, right, meta = contextual_pair(before, after, event)
    for context in (left, right):
        assert "package p;" in context and "state = 1" in context
        assert "neighborBefore" in context and "neighborAfter" in context
        assert "farBefore" not in context and "farAfter" not in context
        assert structural.valid_java(context)
    events = matrix.ex.detect({**base, "before": left}, right, tmp_path / "cropped", tool)["events"]
    cropped_event = structural.select_event(events, "Rename Parameter", description=event["description"])
    result = structural.evaluate({**base, "before": left, "target_event": structural.identity(cropped_event)}, right,
                                 tmp_path / "accepted", tool)
    assert result["structural_success"]
    assert meta["context_before_bytes"] < meta["before_bytes"]


def test_multiple_events_choose_explicit_dataset_target_not_first_event():
    def event(name, line):
        return {"type": "Rename Variable", "description": "Rename Variable x : int to " + name + " : int in method f()",
                "left": [{"startLine": line, "startColumn": 1}], "right": [{"codeElement": name + " : int"}]}
    first, desired = event("unrelated", 1), event("requested", 5)
    assert structural.select_event([first, desired], "Rename Variable", description=desired["description"]) == desired
    with pytest.raises(ValueError, match="missing"):
        structural.select_event([first], "Extract Variable")


def test_extract_variable_checks_requested_expression_not_just_new_name(tmp_path):
    from llm_ontology.benchmarks.refactoring_prepare import tool_identity
    tool = tool_identity(matrix.load_plan(1))
    before = "class A { int f(){return g()+h();} int g(){return 1;} int h(){return 2;} }"
    gold = "class A { int f(){int value=g(); return value+h();} int g(){return 1;} int h(){return 2;} }"
    wrong = "class A { int f(){int value=h(); return g()+value;} int g(){return 1;} int h(){return 2;} }"
    base = {"before": before, "operation": "Extract Variable", "file_path": "A.java", "class_name": "A",
            "target": {"method": "f", "start": 1, "end": 1}}
    event = structural.select_event(matrix.ex.detect(base, gold, tmp_path / "detect", tool)["events"], "Extract Variable")
    case = {**base, "target_event": structural.identity(event), "extraction_expression": "g()"}
    assert structural.evaluate(case, gold, tmp_path / "gold", tool)["structural_success"]
    assert not structural.evaluate(case, wrong, tmp_path / "wrong", tool)["structural_success"]
