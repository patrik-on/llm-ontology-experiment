"""Complete ledger/identity/coverage verification; report only, zero model calls."""

from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.methods2test_batch import ARMS, verify, selection, read
from llm_ontology.benchmarks.methods2test_statistics import aggregate


def finalize(root):
    verify(root)
    selected = selection(root)
    ids = selected["ids"]
    expected = {(i, a) for i in ids for a in ARMS}
    ledger = []
    references = [
        read(root / "cases" / i / "raw-private.json")["raw"]["test_case"]["body"] for i in ids
    ]
    for p in sorted(root.glob("cases/*/predictions/*/dispatch.json")):
        d = read(p)
        pair = (d["id"], d["arm"])
        if pair not in expected or not d["charged_to_budget"]:
            raise ValueError("unplanned_or_duplicate_dispatch")
        expected.remove(pair)
        if any(g in d["request"]["prompt"] for g in references):
            raise ValueError("gold_entered_prompt")
        completion = p.parent / "completion.json"
        if not completion.exists():
            raise ValueError("unfinished_charged_cell")
        ledger.append(
            {
                "id": pair[0],
                "arm": pair[1],
                "dispatch_sha256": file_sha256(p),
                "completion_sha256": file_sha256(completion),
            }
        )
    if expected or len(ledger) != len(ids) * len(ARMS):
        raise ValueError("incomplete_400_cell_matrix")
    for ident in ids:
        cr = root / "cases" / ident
        p = read(cr / "prepared.json")
        ref = read(cr / "reference-coverage/coverage.json")
        if ref["status"] != "passed" or not ref["focal_invoked"] or not ref["coverage"]:
            raise ValueError("invalid_reference_control")
        if file_sha256(cr / "reference-private.java") != p["reference_sha256"]:
            raise ValueError("reference_changed")
        for arm in ARMS:
            out = cr / "predictions" / arm
            if not (out / "generated.java").exists():
                continue
            m = read(out / "metrics.json")
            if (
                file_sha256(out / "generated.java")
                != read(out / "generation.json")["source_sha256"]
            ):
                raise ValueError("model_source_changed")
            if m["statuses"] == ["source_review_rejected"]:
                continue
            if len(m["outcomes"]) != 2:
                raise ValueError("missing_two_fresh_executions")
            for result in m["outcomes"]:
                if result["status"] != "passed" and result["coverage"] is not None:
                    raise ValueError("failed_coverage_credited")
                coverage = result["coverage"] or result.get("diagnostic_coverage")
                if coverage and coverage["status"] == "measured":
                    if coverage["method"]["descriptor"] != ref["coverage"]["method"]["descriptor"]:
                        raise ValueError("wrong_overload")
                    for scope in ["method", "class"]:
                        for metric in ["line", "branch"]:
                            if (
                                coverage[scope]["counters"][metric]["total"]
                                != ref["coverage"][scope]["counters"][metric]["total"]
                            ):
                                raise ValueError("production_denominator_changed")
    result = aggregate(root)
    result["protocol"] = "methods2test_eval_hundred_v1"
    result["reference_summary"] = {}
    for scope in ["method", "class"]:
        result["reference_summary"][scope] = {}
        for metric in ["line", "branch"]:
            counts = [
                ref[scope]["counters"][metric] for ref in result["reference_coverage"].values()
            ]
            applicable = [c for c in counts if c["total"] and c["ratio"] is not None]
            covered = sum(c["covered"] for c in applicable)
            total = sum(c["total"] for c in applicable)
            result["reference_summary"][scope][metric] = {
                "covered": covered,
                "total": total,
                "pooled_ratio": covered / total if total else None,
                "case_macro": sum(c["ratio"] for c in applicable) / len(applicable)
                if applicable
                else None,
                "applicable_cases": len(applicable),
                "not_applicable": len(counts) - len(applicable),
            }
    failures = {arm: Counter() for arm in ARMS}
    for row in result["paired_matrix"]:
        status = row.get("statuses", [])
        error = (row.get("failure") or {}).get("error", "")
        row["failure_category"] = (
            "passed"
            if row.get("class_pass")
            else status[0]
            if status
            else "body_java_syntax_rejection"
            if "balanced Java statements" in error
            else "schema_or_protocol_rejection"
        )
        failures[row["arm"]][row["failure_category"]] += 1
        row.pop("failure", None)
    result["failure_categories"] = {arm: dict(counts) for arm, counts in failures.items()}
    result["identity_hashing"] = read(root / "identity_hashing.json")
    result["ft_load"] = [read(p) for p in root.glob("ft_load-*.json")]
    result["verified_ledger"] = ledger
    result["projects"] = {p["id"]: p["repository"] for p in selected["cases"]}
    result["project_counts"] = dict(Counter(result["projects"].values()))
    result["preparation"] = read(root / "preparation_progress.json")
    result["freeze_sha256"] = file_sha256(root / "freeze.json")
    result["reference_is_independent"] = True
    result["generation_budget_complete"] = True
    write_json(root / "reports/final.json", result)
    write_json(Path("docs/experiments/methods2test_eval_hundred_v1_results.json"), result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id

    validate_evaluation_run_id(a.run_id)
    result = finalize((Path("artifacts/evaluation/runs") / a.run_id).resolve())
    print("VERIFIED", len(result["verified_ledger"]), "calls")


if __name__ == "__main__":
    main()
