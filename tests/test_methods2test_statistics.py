"""Pure stored-evidence fixtures: no JVM, model, network or ignored run required."""

from copy import deepcopy
import json
import xml.etree.ElementTree as ET

import pytest

from llm_ontology.benchmarks.methods2test_statistics import (
    ARMS,
    Z95,
    aggregate,
    per_test_outcomes,
    wilson95,
)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def counter(covered, total):
    return {
        "covered": covered,
        "missed": total - covered,
        "total": total,
        "ratio": covered / total if total else None,
        "reason": None if total else "zero_total",
    }


def coverage(lines=2, branches=2, line_covered=None, branch_covered=None):
    counts = {
        "line": counter(lines if line_covered is None else line_covered, lines),
        "branch": counter(branches if branch_covered is None else branch_covered, branches),
    }
    return {s: {"counters": deepcopy(counts)} for s in ("method", "class")}


def cell(root, ident, arm, passed=True, cov=None, *, assembled=True, attempted=True):
    out = root / "cases" / ident / "predictions" / arm
    out.mkdir(parents=True, exist_ok=True)
    if attempted:
        put(out / "dispatch.json", {"id": ident, "arm": arm, "charged_to_budget": True})
    if assembled:
        (out / "generated.java").write_text("// fixture only", encoding="utf-8")
        put(out / "bodies.json", {"testCase1": "", "testCase2": ""})
        put(
            out / "metrics.json",
            {
                "class_pass": passed,
                "compiled": True,
                "positive_nonaborted_execution": True,
                "syntax_parse": True,
                "focal_invoked_accepted": passed,
                "coverage": cov,
                "coverage_reason": None,
                "diagnostic_coverage": None,
                "repeat_stable": True,
                "tests_first_run": {"tests_started": 2},
            },
        )
    return out


def fixture(root, n=3):
    ids = [f"case{i}" for i in range(n)]
    put(root / "selection.json", {"ids": ids})
    for i in ids:
        put(root / "cases" / i / "reference-coverage/coverage.json", {"coverage": coverage()})
        for arm in ARMS:
            cell(root, i, arm, cov=coverage())
    return ids


def metric(report, arm=ARMS[0], scope="method", kind="line"):
    return report["arms"][arm]["coverage"][scope][kind]


@pytest.mark.parametrize("n", [0, 1, 3, 7])
def test_arbitrary_case_count_and_no_default_writes(tmp_path, n):
    fixture(tmp_path, n)
    report = aggregate(tmp_path)
    assert report["case_count"] == n
    assert report["actual_calls"] == report["max_actual_calls"] == n * 4
    assert len(report["paired_matrix"]) == n * 4
    assert len(report["paired_comparisons"]) == 6
    assert not (tmp_path / "reports").exists()
    for arm in ARMS:
        assert report["arms"][arm]["class_pass"]["denominator"] == n
        assert report["arms"][arm]["class_pass"]["rate"] == (1 if n else None)


@pytest.mark.parametrize("missing_counter", [False, True])
def test_branchless_reference_excluded_from_macro(tmp_path, missing_counter):
    ids = fixture(tmp_path)
    ref = coverage()
    empty = (
        {"covered": None, "missed": None, "total": None, "ratio": None, "reason": "missing_counter"}
        if missing_counter
        else counter(0, 0)
    )
    for scope in ("method", "class"):
        ref[scope]["counters"]["branch"] = deepcopy(empty)
    put(tmp_path / "cases" / ids[0] / "reference-coverage/coverage.json", {"coverage": ref})
    cell(tmp_path, ids[0], ARMS[0], cov=ref)
    cell(tmp_path, ids[1], ARMS[0], cov=coverage(branch_covered=1))
    cell(tmp_path, ids[2], ARMS[0], passed=False, cov=None)
    report = aggregate(tmp_path)
    for scope in ("method", "class"):
        m = metric(report, scope=scope, kind="branch")
        assert m["all_attempt_applicable_cases"] == 2
        assert m["not_applicable_cases"] == 1
        assert m["all_attempt_success_credit_case_macro"] == 0.25
        assert m["all_attempt_success_credit_pooled_ratio"] == 0.25
        assert m["conditional_case_macro"] == 0.5
        paired = report["paired_comparisons"][0]["coverage_success_credit"][scope]["branch"]
        assert paired["not_applicable_cases"] == [ids[0]]
        assert paired["paired_cases"] == 2


def test_all_branchless_is_na_not_zero_or_one(tmp_path):
    ids = fixture(tmp_path, 1)
    cov = coverage(branches=0)
    put(tmp_path / "cases" / ids[0] / "reference-coverage/coverage.json", {"coverage": cov})
    for a in ARMS:
        cell(tmp_path, ids[0], a, cov=cov)
    m = metric(aggregate(tmp_path), kind="branch")
    assert m["all_attempt_applicable_cases"] == 0
    assert m["all_attempt_success_credit_case_macro"] is None
    assert m["all_attempt_success_credit_pooled_ratio"] is None
    assert m["conditional_case_macro"] is None


def test_missing_passing_coverage_is_infrastructure_not_zero(tmp_path):
    ids = fixture(tmp_path)
    cell(tmp_path, ids[1], ARMS[0], passed=True, cov=None)
    report = aggregate(tmp_path)
    assert report["arms"][ARMS[0]]["class_pass"]["rate"] == 1
    for scope in ("method", "class"):
        for kind in ("line", "branch"):
            m = metric(report, scope=scope, kind=kind)
            assert m["all_attempt_success_credit_case_macro"] is None
            assert m["all_attempt_success_credit_pooled_ratio"] is None
            assert m["all_attempt_success_credit_covered"] is None
            assert m["credit_unavailable_reason"] == "passing_class_missing_instrumentation"
            assert m["conditional_case_macro"] == 1  # explicitly measured subset
    row = next(r for r in report["paired_matrix"] if r["id"] == ids[1] and r["arm"] == ARMS[0])
    assert row["coverage"] is None
    assert row["coverage_infrastructure_reason"] == "passing_class_missing_instrumentation"
    pair = report["paired_comparisons"][0]["coverage_success_credit"]["method"]["line"]
    assert pair["paired_cases"] == 2
    assert pair["complete_pair_macro_difference"] is None
    assert pair["complete_pair_pooled_difference"] is None
    assert pair["available_pair_subset_only"] is True
    assert pair["unavailable_pairs"][0]["id"] == ids[1]


@pytest.mark.parametrize("malformation", ["missing", "ratio", "total", "missed"])
def test_partial_invalid_or_mismatched_counter_not_zero(tmp_path, malformation):
    ids = fixture(tmp_path, 1)
    cov = coverage()
    if malformation == "missing":
        del cov["method"]["counters"]["branch"]
    elif malformation == "ratio":
        cov["method"]["counters"]["branch"]["ratio"] = 0.1
    elif malformation == "missed":
        cov["method"]["counters"]["branch"]["missed"] = 99
    else:
        cov["method"]["counters"]["branch"] = counter(2, 3)
    cell(tmp_path, ids[0], ARMS[0], cov=cov)
    report = aggregate(tmp_path)
    assert metric(report)["all_attempt_success_credit_case_macro"] == 1
    m = metric(report, kind="branch")
    assert m["all_attempt_success_credit_case_macro"] is None
    assert m["credit_unavailable_cases"] == 1
    assert (
        metric(report, scope="class", kind="branch")["all_attempt_success_credit_case_macro"] == 1
    )


def test_failed_primary_and_diagnostic_coverage_never_credit(tmp_path):
    ids = fixture(tmp_path, 1)
    out = cell(tmp_path, ids[0], ARMS[0], passed=False, cov=coverage())
    ev = json.loads((out / "metrics.json").read_text())
    ev["diagnostic_coverage"] = coverage()
    put(out / "metrics.json", ev)
    report = aggregate(tmp_path)
    m = metric(report)
    assert m["all_attempt_success_credit_case_macro"] == 0
    assert m["all_attempt_success_credit_pooled_ratio"] == 0
    assert m["accepted_measured_cases"] == 0
    assert m["conditional_case_macro"] is None
    row = report["paired_matrix"][0]
    assert row["coverage"] is None
    assert row["diagnostic_coverage"] == row["failed_raw_coverage_diagnostic"] == coverage()


def test_failed_generation_in_denominator_but_undispatched_not_attempt(tmp_path):
    ids = fixture(tmp_path, 3)
    out = tmp_path / "cases" / ids[1] / "predictions" / ARMS[0]
    (out / "generated.java").unlink()
    (out / "metrics.json").unlink()
    put(out / "failure.json", {"error": "bad body"})
    put(out / "completion.json", {"status": "model_output_failure"})
    (tmp_path / "cases" / ids[2] / "predictions" / ARMS[0] / "dispatch.json").unlink()
    report = aggregate(tmp_path)
    stats = report["arms"][ARMS[0]]
    assert stats["actual_calls"] == stats["class_pass"]["denominator"] == 2
    assert stats["unattempted_cases"] == 1
    assert stats["class_pass"]["rate"] == 0.5
    assert metric(report)["all_attempt_success_credit_case_macro"] == 0.5
    assert report["paired_comparisons"][0]["both_attempted_cases"] == 2


def test_missing_evaluation_not_declared_failure(tmp_path):
    fixture(tmp_path, 1)
    out = tmp_path / "cases/case0/predictions" / ARMS[0]
    (out / "metrics.json").unlink()
    report = aggregate(tmp_path)
    stats = report["arms"][ARMS[0]]["class_pass"]
    assert stats["rate"] is None and stats["wilson95"] is None
    assert stats["unknown"] == stats["denominator"] == 1
    assert metric(report)["all_attempt_success_credit_case_macro"] is None


def test_missing_reference_not_branchless(tmp_path):
    fixture(tmp_path, 1)
    (tmp_path / "cases/case0/reference-coverage/coverage.json").unlink()
    m = metric(aggregate(tmp_path), kind="branch")
    assert m["not_applicable_cases"] == 0
    assert m["all_attempt_success_credit_pooled_ratio"] is None
    assert m["credit_unavailable_reason"] == "reference_counter_unavailable"


@pytest.mark.parametrize(
    "successes,n,lo,hi",
    [
        (0, 5, 0, 0.43448246478317476),
        (5, 5, 0.5655175352168252, 1),
        (3, 5, 0.2307242812760128, 0.882379225767352),
    ],
)
def test_wilson95_known_values(successes, n, lo, hi):
    interval = wilson95(successes, n)
    assert interval["lower"] == pytest.approx(lo, abs=1e-12)
    assert interval["upper"] == pytest.approx(hi, abs=1e-12)


def test_wilson_empty_and_invalid():
    assert wilson95(0, 0)["lower"] is None
    for k, n in [(-1, 2), (3, 2), (0, -1)]:
        with pytest.raises(ValueError):
            wilson95(k, n)


def test_paired_pass_difference_uses_case_identity_and_sample_sd(tmp_path):
    ids = fixture(tmp_path, 3)
    # a-b = [1, -1, 1], not a difference of unrelated passing subsets.
    for i, ap, bp in zip(ids, [True, False, True], [False, True, False]):
        cell(tmp_path, i, ARMS[0], passed=ap, cov=coverage() if ap else None)
        cell(tmp_path, i, ARMS[1], passed=bp, cov=coverage() if bp else None)
    pair = aggregate(tmp_path)["paired_comparisons"][0]
    p = pair["class_pass"]
    assert p["paired_cases"] == 3
    assert p["mean_difference"] == pytest.approx(1 / 3)
    assert [r["difference"] for r in p["per_case"]] == [1, -1, 1]
    assert [p["a_higher"], p["b_higher"], p["equal"]] == [2, 1, 0]
    assert p["paired_normal_95"]["standard_error"] == pytest.approx(2 / 3)
    assert p["paired_normal_95"]["lower"] == pytest.approx(1 / 3 - Z95 * 2 / 3)
    assert "not random-sample" in p["interpretation"]
    cm = pair["coverage_success_credit"]["method"]["line"]
    assert cm["complete_pair_macro_difference"] == pytest.approx(1 / 3)
    assert cm["complete_pair_pooled_difference"] == pytest.approx(1 / 3)


def test_single_pair_interval_unavailable_and_zero_variance_explicit(tmp_path):
    fixture(tmp_path, 1)
    pair = aggregate(tmp_path)["paired_comparisons"][0]["class_pass"]
    assert pair["paired_normal_95"]["lower"] is None
    assert pair["paired_normal_95"]["reason"] == "fewer_than_two_pairs"
    fixture(tmp_path, 2)
    pair = aggregate(tmp_path)["paired_comparisons"][0]["class_pass"]
    assert pair["paired_normal_95"]["lower"] == pair["paired_normal_95"]["upper"] == 0




def test_generation_metadata_and_optional_output(tmp_path):
    fixture(tmp_path, 1)
    out = tmp_path / "cases/case0/predictions" / ARMS[0]
    put(
        out / "server_response.json",
        {
            "done_reason": "length",
            "prompt_eval_count": 17,
            "eval_count": 9,
            "eval_duration": 2_000_000_000,
            "load_duration": 1_000_000_000,
        },
    )
    target = tmp_path / "new-report/statistics.json"
    report = aggregate(tmp_path, output=target)
    assert json.loads(target.read_text()) == report
    row = report["paired_matrix"][0]
    assert row["truncated"] is True
    assert row["generation_seconds"] == 2
    assert row["input_tokens"] == 17 and row["output_tokens"] == 9
    out = tmp_path / "cases/case0/predictions" / ARMS[1]
    put(
        out / "generation_metadata.json",
        {"output_truncated": True, "input_tokens": 11, "output_tokens": 8},
    )
    row = aggregate(tmp_path)["paired_matrix"][1]
    assert row["truncated"] is True and row["input_tokens"] == 11


@pytest.mark.parametrize("ids", [["a", "a"], ["../escape"], ["a/b"], ["a\\b"], ["."], [4]])
def test_bad_selection_rejected(tmp_path, ids):
    put(tmp_path / "selection.json", {"ids": ids})
    with pytest.raises(ValueError):
        aggregate(tmp_path)


def test_xml_repeat_signature_detects_swapped_failure_and_filters_gold(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    template = (
        '<testsuite><testcase classname="p.GeneratedBodyTests" name="one">{}</testcase>'
        '<testcase classname="p.GeneratedBodyTests" name="two">{}</testcase>'
        '<testcase classname="p.ReferenceTests" name="gold"/></testsuite>'
    )
    failure = '<failure type="AssertionError"/>'
    (a / "TEST-jupiter.xml").write_text(template.format(failure, ""))
    (b / "TEST-jupiter.xml").write_text(template.format("", failure))
    assert per_test_outcomes(a) != per_test_outcomes(b)
    assert [r["status"] for r in per_test_outcomes(a)] == ["failure", "passed"]
    assert len(per_test_outcomes(a, test_class="p.ReferenceTests")) == 1
    assert per_test_outcomes(tmp_path / "missing") == []


def test_xml_order_independent_errors_and_skips(tmp_path):
    path = tmp_path / "TEST-jupiter.xml"
    tests = [
        '<testcase classname="GeneratedBodyTests" name="two"><skipped/></testcase>',
        '<testcase classname="GeneratedBodyTests" name="one"><error type="Setup"/></testcase>',
    ]
    path.write_text("<testsuite>" + "".join(tests) + "</testsuite>")
    before = per_test_outcomes(tmp_path)
    path.write_text("<testsuite>" + "".join(reversed(tests)) + "</testsuite>")
    assert before == per_test_outcomes(tmp_path)
    assert [r["status"] for r in before] == ["error", "skipped"]
    path.write_text("not XML")
    with pytest.raises(ET.ParseError):
        per_test_outcomes(tmp_path)

@pytest.mark.parametrize("status", [None, "assembled"])
def test_unresolved_dispatch_keeps_cost_but_not_failure(tmp_path, status):
    fixture(tmp_path, 1)
    out = tmp_path / "cases/case0/predictions" / ARMS[0]
    (out / "generated.java").unlink()
    (out / "metrics.json").unlink()
    if status:
        put(out / "completion.json", {"status": status})
    report = aggregate(tmp_path)
    stats = report["arms"][ARMS[0]]
    assert stats["actual_calls"] == 1
    assert stats["class_pass"]["unknown"] == 1
    assert stats["class_pass"]["rate"] is None
    assert metric(report)["all_attempt_success_credit_case_macro"] is None
    assert report["paired_comparisons"][0]["class_pass"]["unavailable_pairs"] == 1


def test_repeat_warning_exposes_both_coverages_without_rescoring(tmp_path):
    fixture(tmp_path, 1)
    out = tmp_path / "cases/case0/predictions" / ARMS[0]
    ev = json.loads((out / "metrics.json").read_text())
    first, second = coverage(line_covered=1), coverage(line_covered=2)
    ev.update(coverage=first, outcomes=[{"coverage": first}, {"coverage": second}],
              per_test_outcomes_repeat_equal=False)
    put(out / "metrics.json", ev)
    report = aggregate(tmp_path)
    row = report["paired_matrix"][0]
    assert row["class_pass"] is True and row["coverage"] == first
    assert row["repeat_diagnostics"]["coverage_by_repeat"] == [first, second]
    assert row["repeat_diagnostics"]["warnings"] == ["coverage_repeat_mismatch", "test_outcomes_repeat_mismatch"]
    assert metric(report)["all_attempt_success_credit_case_macro"] == 0.5
    assert report["arms"][ARMS[0]]["repeat_diagnostics"]["coverage_mismatch_cases"] == 1

@pytest.mark.parametrize("status", ["model_output_failure", "infrastructure_failure"])
def test_completed_failures_preserve_existing_scoring_policy(tmp_path, status):
    fixture(tmp_path, 1)
    out = tmp_path / "cases/case0/predictions" / ARMS[0]
    (out / "generated.java").unlink()
    (out / "metrics.json").unlink()
    put(out / "completion.json", {"status": status})
    report = aggregate(tmp_path)
    row = report["paired_matrix"][0]
    assert row["class_pass"] is False
    assert row["generation_status"] == status
    assert report["arms"][ARMS[0]]["class_pass"]["rate"] == 0
