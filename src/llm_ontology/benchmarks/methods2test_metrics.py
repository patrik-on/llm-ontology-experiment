"""Coverage/correctness reporting for the bounded extracted-method validation pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.methods2test_pilot import ARMS, read, runtime
from llm_ontology.evaluation.coverage_runner import run_jacoco_coverage
from llm_ontology.ingestion.java import JavaParser


def measure(source, prepared, output):
    c = runtime()
    pins = read(Path("configs/evaluation/jacoco_v1.json"))
    # Tool paths are separately pinned by the coverage runner's embedded SHA-256.
    agent = Path("/home/patrik/benchmark-work/downloads/org.jacoco.agent-0.8.13-runtime.jar")
    cli = Path("/home/patrik/benchmark-work/downloads/org.jacoco.cli-0.8.13-nodeps.jar")
    if not pins:
        raise ValueError("Missing coverage manifest")
    return run_jacoco_coverage(source, prepared["revision"], output=output,
        java_home=c.java_home, junit_jar=c.junit_jar, junit_sha256=c.junit_sha256,
        agent_jar=agent, cli_jar=cli, focal_class=prepared["focal_class"], focal_method=prepared["focal_method"])


def reference(root):
    for ident in read(root / "selection.json")["ids"]:
        cr = root / "cases" / ident
        if (cr / "reference-coverage/coverage.json").exists():
            continue
        prepared = read(cr / "prepared.json")
        source = (cr / "reference-private.java").read_text()
        if file_sha256(cr / "reference-private.java") != prepared["reference_sha256"]:
            raise ValueError("Reference changed")
        result = measure(source, prepared, cr / "reference-coverage")
        if result["status"] != "passed" or result["coverage"] is None or not result["focal_invoked"]:
            raise ValueError("Reference coverage/focal execution failed: " + ident)
        print("REFERENCE_COVERAGE", ident, result["coverage"]["method"]["counters"], flush=True)


def evaluate(root, reviews):
    parser = JavaParser()
    for ident in read(root / "selection.json")["ids"]:
        cr = root / "cases" / ident
        prepared = read(cr / "prepared.json")
        for arm in ARMS:
            out = cr / "predictions" / arm
            if not (out / "generated.java").exists():
                continue
            if (out / "metrics.json").exists():
                continue
            key = ident + "/" + arm
            digest = file_sha256(out / "generated.java")
            if digest != reviews.get(key) or digest != read(out / "generation.json")["source_sha256"]:
                raise ValueError("Missing matching reviewed-source hash: " + key)
            source = (out / "generated.java").read_text()
            write_json(out / "review.json", {"source_sha256": digest, "reviewed_local_execution": True, "security_sandbox": False})
            results = []
            for i in range(2):
                path = out / ("coverage-" + str(i))
                results.append(read(path / "coverage.json") if (path / "coverage.json").exists() else measure(source, prepared, path))
            summaries = [r["execution"].get("console_summary", {}) for r in results]
            outcomes = [r["status"] for r in results]
            # Presence only, NOT semantic assertion quality or proof against vacuity.
            lexical_assertions = len(re.findall(r"\b(?:assert[A-Z]\w*|fail)\s*\(",
                "\n".join(read(out / "bodies.json").values())))
            result = {"id": ident, "arm": arm, "source_sha256": digest,
                "syntax_parse": parser.parse(source).parse_success, "assertion_calls_lexical_diagnostic": lexical_assertions,
                "compiled": all(r["execution"].get("compile", {}).get("returncode") == 0 for r in results),
                "positive_nonaborted_execution": all(s.get("tests_started", 0) > 0 and s.get("tests_aborted", 0) == 0 and s.get("containers_failed", 0) == 0 for s in summaries),
                "class_pass": all(o == "passed" for o in outcomes), "statuses": outcomes,
                "repeat_stable": outcomes[0] == outcomes[1] and summaries[0] == summaries[1],
                "tests_first_run": summaries[0], "focal_invoked_accepted": all(r["focal_invoked"] is True for r in results),
                "coverage": results[0]["coverage"] if all(o == "passed" for o in outcomes) else None,
                "coverage_reason": results[0]["coverage_reason"],
                "diagnostic_coverage": results[0]["diagnostic_coverage"],
                "repeat_coverage_equal": results[0]["coverage"] == results[1]["coverage"],
                "outcomes": results}
            write_json(out / "metrics.json", result)
            print("EVALUATED", ident, arm, outcomes, flush=True)


def aggregate(root):
    ids = read(root / "selection.json")["ids"]
    rows = []
    refs = {}
    for ident in ids:
        p = root / "cases" / ident / "reference-coverage/coverage.json"
        refs[ident] = read(p)["coverage"] if p.exists() else None
        for arm in ARMS:
            out = root / "cases" / ident / "predictions" / arm
            ev = read(out / "metrics.json") if (out / "metrics.json").exists() else {}
            server = read(out / "server_response.json") if (out / "server_response.json").exists() else {}
            ft = read(out / "generation_metadata.json") if (out / "generation_metadata.json").exists() else {}
            received = read(out / "received.json") if (out / "received.json").exists() else {}
            record = received.get("experiment_record", {})
            r = {"id": ident, "arm": arm, "actual_calls": int((out / "dispatch.json").exists()),
                 "body_schema": (out / "bodies.json").exists(), "assembled": (out / "generated.java").exists(),
                 "truncated": server.get("done_reason") == "length" or ft.get("output_truncated", False),
                 "finish_reason": server.get("done_reason", ft.get("finish_reason")),
                 "input_tokens": server.get("prompt_eval_count", ft.get("input_tokens")),
                 "output_tokens": server.get("eval_count", ft.get("output_tokens")),
                 "generation_seconds": server.get("eval_duration", 0) / 1e9 if "eval_duration" in server else received.get("dispatch_to_return_seconds"),
                 "load_seconds": server.get("load_duration", 0) / 1e9 if "load_duration" in server else None,
                 "retrieval_seconds": record.get("retrieval_trace", {}).get("total_latency_ms", 0) / 1000 if record else None,
                 "failure": read(out / "failure.json") if (out / "failure.json").exists() else None,
                 **{k: v for k, v in ev.items() if k not in ["outcomes", "source_sha256", "id", "arm"]}}
            if not ev:
                r.update(class_pass=False, compiled=False, positive_nonaborted_execution=False,
                         coverage=None, coverage_reason="generation_not_assembled", syntax_parse=False,
                         focal_invoked_accepted=False, repeat_stable=None, tests_first_run={})
            rows.append(r)
    arms = {}
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm]
        stats = {"actual_calls": sum(r["actual_calls"] for r in rs), "cases": 5}
        for key in ["body_schema", "assembled", "truncated", "syntax_parse", "compiled", "positive_nonaborted_execution", "class_pass", "focal_invoked_accepted"]:
            n = sum(bool(r.get(key)) for r in rs)
            stats[key] = {"count": n, "denominator": 5, "rate": n / 5}
        stats["repeat_stable"] = {"count": sum(r.get("repeat_stable") is True for r in rs), "measured": sum(r.get("repeat_stable") is not None for r in rs)}
        stats["tests_first_run"] = {key: sum(r.get("tests_first_run", {}).get(key, 0) for r in rs) for key in ["tests_started", "tests_successful", "tests_failed", "tests_aborted", "tests_skipped"]}
        stats["assertion_presence"] = {"classes_with_lexical_calls": sum(r.get("assertion_calls_lexical_diagnostic", 0) > 0 for r in rs), "diagnostic_only": True}
        stats["coverage"] = {}
        for scope in ["method", "class"]:
            stats["coverage"][scope] = {}
            for metric in ["line", "branch"]:
                counts = [r["coverage"][scope]["counters"][metric] for r in rs if r.get("coverage")]
                measured = [x for x in counts if x["ratio"] is not None]
                denominators = [refs[i][scope]["counters"][metric] for i in ids if refs[i]]
                total = sum(d["total"] or 0 for d in denominators)
                covered = sum(d["covered"] or 0 for d in measured)
                stats["coverage"][scope][metric] = {
                    "accepted_measured_cases": len(measured), "conditional_case_macro": sum(d["ratio"] for d in measured) / len(measured) if measured else None,
                    "conditional_pooled_covered": covered, "conditional_pooled_total": sum(d["total"] for d in measured),
                    "conditional_pooled_ratio": covered / sum(d["total"] for d in measured) if measured and sum(d["total"] for d in measured) else None,
                    "all_attempt_success_credit_covered": covered, "all_attempt_reference_denominator": total,
                    "all_attempt_success_credit_pooled_ratio": covered / total if total else None,
                    "all_attempt_success_credit_case_macro": sum(r["coverage"][scope]["counters"][metric]["ratio"] or 0 for r in rs if r.get("coverage")) / 5,
                    "missing_measurement_not_zero": True,
                    "credit_policy": "Failed/unassembled class gets zero success CREDIT against reference denominator, NOT a claimed measured zero coverage."}
        arms[arm] = stats
    result = {"protocol": "methods2test_eval_five_v1", "role": "pilot_validation", "split": "official eval", "cases": ids,
        "actual_calls": sum(r["actual_calls"] for r in rows), "max_actual_calls": 20, "attempts_per_cell": 1, "retries": 0, "repairs": 0,
        "reference_coverage": refs, "arms": arms, "paired_matrix": rows, "bug_detection": "not_applicable_no_buggy_revisions",
        "scientific_final_score": False, "coverage": "real JaCoCo 0.8.13; production focal method/class only; two fresh runs; no gold mixed into generated-test runs"}
    write_json(root / "reports/aggregate.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["reference", "evaluate", "report"])
    p.add_argument("--run-id", required=True)
    p.add_argument("--review-manifest", type=Path)
    a = p.parse_args()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
    validate_evaluation_run_id(a.run_id)
    root = (Path("artifacts/evaluation/runs") / a.run_id).resolve()
    if a.action == "reference":
        reference(root)
    elif a.action == "evaluate":
        if not a.review_manifest:
            raise ValueError("Review manifest required")
        evaluate(root, read(a.review_manifest))
    else:
        result = aggregate(root)
        print(json.dumps({"actual_calls": result["actual_calls"], "arms": result["arms"]}, indent=2))


if __name__ == "__main__":
    main()
