"""Model-free statistics for arbitrary Methods2Test case counts, one call per cell.

Read the current matrix selection/generation/metrics/coverage layout.
aggregate(root) is read-only; optionally
supply output to persist a new report. Unattempted cells are explicit, not failed
attempts. Failed attempts earn zero *success credit*, never measured zero coverage.
Convenience-selected cases are not random independent project samples: intervals
below are descriptive and do not justify population, causal or ranking inference.
"""

from __future__ import annotations

from itertools import combinations
import json
from math import isfinite, sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any
import xml.etree.ElementTree as ET

from llm_ontology.benchmarks.paired_tests import holm, mcnemar_exact, wilcoxon_signed_rank

ARMS = ("qwen_base", "onto_project", "skills", "skills_onto", "rag_single",
        "ft_testing", "ft_v3_onto", "ft_onto")
SCOPES = ("method", "class")
COUNTERS = ("line", "branch")
Z95 = 1.959963984540054
INTERPRETATION = (
    "Convenience-selected, possibly project-clustered cases. Exact paired tests "
    "(McNemar for class pass, Wilcoxon signed-rank for coverage credit, Holm across arm pairs) "
    "are conditional on the selected cases; not random-sample population inference or a causal comparison."
)


def _read(path: Path, *, optional: bool = False) -> dict:
    if optional and not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def wilson95(successes: int, n: int) -> dict:
    """Two-sided Wilson score interval (z=1.95996), including 0/n and n/n."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("Require 0 <= successes <= n")
    if not n:
        return {"lower": None, "upper": None, "confidence": 0.95, "method": "wilson_score"}
    p = successes / n
    scale = 1 + Z95**2 / n
    center = (p + Z95**2 / (2 * n)) / scale
    half = Z95 * sqrt(p * (1 - p) / n + Z95**2 / (4 * n**2)) / scale
    return {
        "lower": max(0.0, center - half),
        "upper": min(1.0, center + half),
        "confidence": 0.95,
        "method": "wilson_score",
    }


def _rate(rows: list[dict], key: str) -> dict:
    n = len(rows)
    count = sum(r.get(key) is True for r in rows)
    unknown = sum(r.get(key) is None for r in rows)
    return {
        "count": count,
        "denominator": n,
        "unknown": unknown,
        "rate": count / n if n and not unknown else None,
        "wilson95": wilson95(count, n) if not unknown else None,
        "interpretation": INTERPRETATION,
    }


def _counter(coverage: dict | None, scope: str, metric: str) -> dict:
    return ((coverage or {}).get(scope) or {}).get("counters", {}).get(metric) or {}


def _reference_state(reference: dict | None, scope: str, metric: str) -> tuple:
    c = _counter(reference, scope, metric)
    if (
        reference
        and metric == "branch"
        and (
            (c.get("total") == 0 and c.get("reason") in (None, "zero_total"))
            or (c.get("total") is None and c.get("reason") == "missing_counter")
        )
    ):
        return False, 0, "not_applicable_branchless"
    total = c.get("total")
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or total <= 0
        or c.get("reason") not in (None, "zero_total")
    ):
        return None, None, "reference_counter_unavailable"
    return True, total, None


def _measurement(row: dict, scope: str, metric: str) -> tuple:
    if row.get("class_pass") is not True:
        return None, None, "class_not_passed"
    c = _counter(row.get("coverage"), scope, metric)
    total, covered, ratio = (c.get(k) for k in ("total", "covered", "ratio"))
    if not row.get("coverage"):
        return None, None, "passing_class_missing_instrumentation"
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or total <= 0
        or not isinstance(covered, int)
        or isinstance(covered, bool)
        or not 0 <= covered <= total
        or c.get("missed") != total - covered
        or not isinstance(ratio, (float, int))
        or isinstance(ratio, bool)
        or not isfinite(ratio)
        or abs(ratio - covered / total) > 1e-9
        or c.get("reason") is not None
    ):
        return None, None, "passing_class_missing_or_invalid_counter"
    return covered, total, None


def _credit(row: dict, reference: dict | None, scope: str, metric: str) -> dict:
    applicable, total, reason = _reference_state(reference, scope, metric)
    result = {
        "applicable": applicable,
        "reference_total": total,
        "covered": None,
        "ratio": None,
        "reason": reason,
    }
    if applicable is not True:
        return result
    if row.get("class_pass") is None:
        return {**result, "reason": "evaluation_missing"}
    if row.get("class_pass") is not True:
        return {**result, "covered": 0, "ratio": 0.0, "reason": "failed_class_zero_success_credit"}
    covered, actual_total, reason = _measurement(row, scope, metric)
    if reason:
        return {**result, "reason": reason}
    if total != actual_total:
        return {**result, "reason": "production_denominator_mismatch"}
    return {**result, "covered": covered, "ratio": covered / total, "reason": None}


def _coverage_summary(rows: list[dict], references: dict, scope: str, metric: str) -> dict:
    credits = [_credit(r, references.get(r["id"]), scope, metric) for r in rows]
    applicable = [c for c in credits if c["applicable"] is True]
    unavailable = [
        c
        for c in credits
        if c["applicable"] is None or (c["applicable"] is True and c["ratio"] is None)
    ]
    measurements = []
    for row, credit in zip(rows, credits):
        covered, total, reason = _measurement(row, scope, metric)
        if reason is None and credit["applicable"] is not False:
            if credit["reason"] != "production_denominator_mismatch":
                measurements.append((covered, total))
    covered = sum(c for c, _ in measurements)
    measured_total = sum(t for _, t in measurements)
    reference_total = sum(c["reference_total"] for c in applicable)
    known_covered = sum(c["covered"] for c in applicable if c["covered"] is not None)
    complete = not unavailable
    return {
        "accepted_measured_cases": len(measurements),
        "conditional_case_macro": mean(c / t for c, t in measurements) if measurements else None,
        "conditional_pooled_covered": covered,
        "conditional_pooled_total": measured_total,
        "conditional_pooled_ratio": covered / measured_total if measured_total else None,
        "all_attempt_cases": len(rows),
        "all_attempt_applicable_cases": len(applicable),
        "not_applicable_cases": sum(c["applicable"] is False for c in credits),
        "all_attempt_reference_denominator": reference_total
        if all(c["applicable"] is not None for c in credits)
        else None,
        "all_attempt_success_credit_covered": known_covered if complete else None,
        "all_attempt_success_credit_pooled_ratio": known_covered / reference_total
        if complete and reference_total
        else None,
        "all_attempt_success_credit_case_macro": mean(c["ratio"] for c in applicable)
        if complete and applicable
        else None,
        "credit_unavailable_cases": len(unavailable),
        "credit_unavailable_reasons": sorted({c["reason"] for c in unavailable}),
        "credit_unavailable_reason": unavailable[0]["reason"] if unavailable else None,
        "known_success_credit_covered_diagnostic": known_covered,
        "missing_measurement_not_zero": True,
        "credit_policy": "Failed classes receive zero success CREDIT; raw failed coverage is diagnostic only. "
        "Passing measurement gaps invalidate credit aggregates; branchless references are N/A, excluded from macro denominators.",
    }


def _paired_summary(values: list[tuple[str, float, float]], kind: str = "continuous") -> dict:
    differences = [a - b for _, a, b in values]
    n = len(differences)
    delta = mean(differences) if n else None
    se = stdev(differences) / sqrt(n) if n > 1 else None
    return {
        "paired_cases": n,
        "mean_difference": delta,
        "difference_percentage_points": delta * 100 if delta is not None else None,
        "a_higher": sum(d > 0 for d in differences),
        "b_higher": sum(d < 0 for d in differences),
        "equal": sum(d == 0 for d in differences),
        "paired_normal_95": {
            "lower": delta - Z95 * se if se is not None else None,
            "upper": delta + Z95 * se if se is not None else None,
            "standard_error": se,
            "confidence": 0.95,
            "method": "mean_paired_difference_plus_minus_z_sample_sd_over_sqrt_n",
            "reason": "fewer_than_two_pairs" if n < 2 else None,
        },
        "per_case": [{"id": i, "a": a, "b": b, "difference": a - b} for i, a, b in values],
        "significance": (
            mcnemar_exact(sum(d > 0 for d in differences), sum(d < 0 for d in differences))
            if kind == "binary" else wilcoxon_signed_rank(differences)
        ),
        "interpretation": INTERPRETATION,
    }


def paired_comparisons(rows: list[dict], references: dict, ids: list[str], arms=ARMS,
                       pairs=None) -> list[dict]:
    """Pair by original case identity, never by arm rate or observed pass subset.

    ``pairs`` are the predeclared (A, B) comparisons; Holm runs across exactly those.
    Without them every arm combination is compared."""
    cells = {(r["id"], r["arm"]): r for r in rows}
    result = []
    for a, b in (pairs if pairs is not None else combinations(arms, 2)):
        pairs = [
            (i, cells[i, a], cells[i, b])
            for i in ids
            if cells[i, a]["actual_calls"] and cells[i, b]["actual_calls"]
        ]
        observed = [
            (i, float(x["class_pass"]), float(y["class_pass"]))
            for i, x, y in pairs
            if x.get("class_pass") is not None and y.get("class_pass") is not None
        ]
        comparison = {
            "arm_a": a,
            "arm_b": b,
            "direction": "a_minus_b",
            "both_attempted_cases": len(pairs),
            "unattempted_pair_cases": len(ids) - len(pairs),
            "class_pass": _paired_summary(observed, "binary"),
            "coverage_success_credit": {},
        }
        comparison["class_pass"]["unavailable_pairs"] = len(pairs) - len(observed)
        comparison["class_pass"]["available_pair_subset_only"] = len(pairs) != len(observed)
        comparison["class_pass"]["complete_pair_mean_difference"] = (
            comparison["class_pass"]["mean_difference"] if len(pairs) == len(observed) else None
        )
        for scope in SCOPES:
            comparison["coverage_success_credit"][scope] = {}
            for metric in COUNTERS:
                values, na, unknown, ca, cb, totals = [], [], [], [], [], []
                for i, x, y in pairs:
                    xc = _credit(x, references.get(i), scope, metric)
                    yc = _credit(y, references.get(i), scope, metric)
                    if xc["applicable"] is False:
                        na.append(i)
                    elif xc["ratio"] is None or yc["ratio"] is None:
                        unknown.append(
                            {"id": i, "a_reason": xc["reason"], "b_reason": yc["reason"]}
                        )
                    else:
                        values.append((i, xc["ratio"], yc["ratio"]))
                        ca.append(xc["covered"])
                        cb.append(yc["covered"])
                        totals.append(xc["reference_total"])
                item = _paired_summary(values)
                denominator = sum(totals)
                item.update(
                    not_applicable_cases=na,
                    unavailable_pairs=unknown,
                    available_pair_subset_only=bool(unknown),
                    complete_pair_macro_difference=item["mean_difference"] if not unknown else None,
                    complete_pair_pooled_difference=(sum(ca) - sum(cb)) / denominator
                    if denominator and not unknown
                    else None,
                    reference_denominator=denominator if not unknown else None,
                )
                comparison["coverage_success_credit"][scope][metric] = item
        result.append(comparison)
    _apply_holm(result)
    return result


def _apply_holm(result: list[dict]) -> None:
    """Holm correction across the arm pairs, separately for each metric family."""
    families = [("class_pass",)] + [
        ("coverage_success_credit", scope, metric) for scope in SCOPES for metric in COUNTERS
    ]
    for path in families:
        items = {}
        for index, comparison in enumerate(result):
            item = comparison
            for key in path:
                item = item[key]
            items[str(index)] = item
        adjusted = holm({k: v["significance"]["p_value"] for k, v in items.items()})
        for key, item in items.items():
            item["significance"].update(adjusted[key])


def per_test_outcomes(reports: Path | str, *, test_class: str | None = None) -> list[dict]:
    """Sorted XML repeat signature; excludes reference classes and ignores timings.

    Use an exact FQN when available; the default matches the frozen generated-class
    convention. Missing XML yields [], which is absence, not positive stability.
    Parse errors propagate rather than being mistaken for passing test outcomes.
    """
    result = []
    for path in sorted(Path(reports).glob("TEST-*.xml")):
        for test in ET.parse(path).getroot().iter("testcase"):
            name = test.get("classname", "")
            if not (
                name == test_class
                if test_class
                else name.rsplit(".", 1)[-1] == "GeneratedBodyTests"
            ):
                continue
            states = [s for s in ("failure", "error", "skipped") if test.find(s) is not None]
            state = test.find(states[0]) if states else None
            result.append(
                {
                    "class": name,
                    "test": test.get("name", ""),
                    "status": states[0] if states else "passed",
                    "type": state.get("type") if state is not None else None,
                }
            )
    return sorted(result, key=lambda r: (r["class"], r["test"], r["status"], r["type"] or ""))


def _row(root: Path, ident: str, arm: str) -> dict:
    out = root / "cases" / ident / "predictions" / arm
    ev = _read(out / "metrics.json", optional=True)
    server = _read(out / "server_response.json", optional=True)
    ft = _read(out / "generation_metadata.json", optional=True)
    received = _read(out / "received.json", optional=True)
    completion = _read(out / "completion.json", optional=True)
    record = received.get("experiment_record") or {}
    assembled = (out / "generated.java").is_file()
    attempted = (out / "dispatch.json").is_file()
    row = {k: v for k, v in ev.items() if k not in ("outcomes", "source_sha256", "id", "arm")}
    row.update(
        id=ident,
        arm=arm,
        actual_calls=int(attempted),
        generation_status=completion.get("status", "interrupted_unresolved" if attempted else "pending"),
        body_schema=(out / "bodies.json").is_file(),
        assembled=assembled,
        truncated=server.get("done_reason") == "length" or ft.get("output_truncated", False),
        finish_reason=server.get("done_reason", ft.get("finish_reason")),
        input_tokens=server.get("prompt_eval_count", ft.get("input_tokens")),
        output_tokens=server.get("eval_count", ft.get("output_tokens")),
        generation_seconds=server["eval_duration"] / 1e9
        if "eval_duration" in server
        else received.get("dispatch_to_return_seconds"),
        load_seconds=server["load_duration"] / 1e9 if "load_duration" in server else None,
        prompt_processing_seconds=server["prompt_eval_duration"] / 1e9
        if "prompt_eval_duration" in server
        else None,
        retrieval_seconds=(record.get("retrieval_trace") or {}).get("total_latency_ms", 0) / 1000
        if record
        else None,
        failure=_read(out / "failure.json", optional=True) or None,
    )
    if not ev:
        # A charged request alone proves cost, not a failed model answer.
        # Preserve the historical policy for completed failures; only unresolved
        # dispatches become unknown. generation_status keeps infra/model distinct.
        terminal_failure = completion.get("status") in {"model_output_failure", "infrastructure_failure"}
        unknown = not attempted or assembled or not terminal_failure
        row.update(
            class_pass=None if unknown else False,
            compiled=None if unknown else False,
            positive_nonaborted_execution=None if unknown else False,
            syntax_parse=None if unknown else False,
            focal_invoked_accepted=None if unknown else False,
            repeat_stable=None,
            tests_first_run={},
            coverage=None,
            coverage_reason="evaluation_missing" if assembled else "generation_not_assembled",
        )
    if not row.get("class_pass"):
        # Defensively prevent malformed stored failed primary coverage earning credit.
        if row.get("coverage") is not None:
            row["failed_raw_coverage_diagnostic"] = row["coverage"]
        row["coverage"] = None
    elif row.get("coverage") is None:
        row["coverage_infrastructure_reason"] = "passing_class_missing_instrumentation"
        row["coverage_reason"] = (
            row.get("coverage_reason") or "passing_class_missing_instrumentation"
        )
    outcomes = ev.get("outcomes", [])
    repeat_coverages = [r.get("coverage") or r.get("diagnostic_coverage") for r in outcomes]
    measured = len(repeat_coverages) == 2 and all(c is not None for c in repeat_coverages)
    coverage_equal = repeat_coverages[0] == repeat_coverages[1] if measured else None
    warnings = []
    if coverage_equal is False or ev.get("repeat_coverage_equal") is False:
        warnings.append("coverage_repeat_mismatch")
    if ev.get("per_test_outcomes_repeat_equal") is False:
        warnings.append("test_outcomes_repeat_mismatch")
    row["repeat_diagnostics"] = {
        "coverage_equal": coverage_equal,
        "coverage_by_repeat": repeat_coverages,
        "test_outcomes_equal": ev.get("per_test_outcomes_repeat_equal"),
        "warnings": warnings,
        "diagnostic_only": True,
        "primary_score_policy_changed": False,
    }
    return row


def aggregate(root: Path | str, *, arms=ARMS, pairs=None,
              output: Path | str | None = None) -> dict[str, Any]:
    """Aggregate existing stored evidence, without generation, execution or old writes.

    All-attempt denominators use actually dispatched cells, including failed calls;
    selected-but-undispatched cells are reported separately. For a complete matrix
    this is exactly the selected case count N for each arm. One dispatch per cell
    is assumed, as in the existing artifact protocol; repeats are not new attempts.
    """
    root = Path(root)
    ids = _read(root / "selection.json")["ids"]
    if (
        not isinstance(ids, list)
        or any(
            not isinstance(i, str)
            or not i
            or Path(i).name != i
            or i in (".", "..")
            or "/" in i
            or chr(92) in i
            for i in ids
        )
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("Selection ids must be unique safe case identifiers")
    arms = tuple(arms)
    if not arms or len(set(arms)) != len(arms) or any(a not in ARMS for a in arms):
        raise ValueError("Require distinct known comparison arms")
    pairs = None if pairs is None else [tuple(p) for p in pairs]
    if pairs is not None and any(len(p) != 2 or p[0] == p[1] or set(p) - set(arms) for p in pairs):
        raise ValueError("Comparison pairs must name two different aggregated arms")
    references = {
        i: _read(root / "cases" / i / "reference-coverage/coverage.json", optional=True).get(
            "coverage"
        )
        for i in ids
    }
    rows = [_row(root, i, a) for i in ids for a in arms]
    by_arm = {}
    for arm in arms:
        rs = [r for r in rows if r["arm"] == arm and r["actual_calls"]]
        stats = {
            "cases": len(ids),
            "actual_calls": len(rs),
            "unattempted_cases": len(ids) - len(rs),
        }
        for key in (
            "body_schema",
            "assembled",
            "truncated",
            "syntax_parse",
            "compiled",
            "positive_nonaborted_execution",
            "class_pass",
            "focal_invoked_accepted",
        ):
            stats[key] = _rate(rs, key)
        stats["repeat_stable"] = {
            "count": sum(r.get("repeat_stable") is True for r in rs),
            "measured": sum(r.get("repeat_stable") is not None for r in rs),
        }
        stats["repeat_diagnostics"] = {
            "coverage_mismatch_cases": sum("coverage_repeat_mismatch" in r["repeat_diagnostics"]["warnings"] for r in rs),
            "test_outcome_mismatch_cases": sum("test_outcomes_repeat_mismatch" in r["repeat_diagnostics"]["warnings"] for r in rs),
            "diagnostic_only": True,
        }
        stats["tests_first_run"] = {
            k: sum((r.get("tests_first_run") or {}).get(k, 0) for r in rs)
            for k in (
                "tests_started",
                "tests_successful",
                "tests_failed",
                "tests_aborted",
                "tests_skipped",
            )
        }
        stats["assertion_presence"] = {
            "classes_with_lexical_calls": sum(
                r.get("assertion_calls_lexical_diagnostic", 0) > 0 for r in rs
            ),
            "diagnostic_only": True,
        }
        stats["coverage"] = {
            s: {m: _coverage_summary(rs, references, s, m) for m in COUNTERS} for s in SCOPES
        }
        by_arm[arm] = stats
    result = {
        "protocol": "methods2test_statistics_v1",
        "role": "pilot_validation",
        "split": "official eval",
        "cases": ids,
        "case_count": len(ids),
        "arms": by_arm,
        "reference_coverage": references,
        "actual_calls": sum(r["actual_calls"] for r in rows),
        "max_actual_calls": len(ids) * len(arms),
        "attempts_per_cell": 1,
        "paired_matrix": rows,
        "paired_comparisons": paired_comparisons(rows, references, ids, arms, pairs),
        "comparison_pairs": "predeclared" if pairs is not None else "all_arm_combinations",
        "bug_detection": "not_applicable_no_buggy_revisions",
        "scientific_final_score": False,
        "denominator_policy": "Actual dispatched cells, including generation failures; unattempted cells explicit, not failures.",
        "interval_interpretation": INTERPRETATION,
    }
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + chr(10),
            encoding="utf-8",
        )
    return result
