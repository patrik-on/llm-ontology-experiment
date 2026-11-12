"""Read-only evidence checks + compact final report; never executes/generates tests."""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from llm_ontology.benchmarks.defects4j_execution import file_sha256, write_json
from llm_ontology.benchmarks.methods2test_metrics import aggregate
from llm_ontology.benchmarks.methods2test_pilot import ARMS, read, verify


def test_outcomes(reports: Path) -> list[dict]:
    result = []
    for p in sorted(reports.glob("TEST-*.xml")):
        root = ET.parse(p).getroot()
        for test in root.iter("testcase"):
            name = test.get("classname", "")
            if not name.endswith(".GeneratedBodyTests"):
                continue
            states = [state for state in ["failure", "error", "skipped"] if test.find(state) is not None]
            result.append({"class": name, "test": test.get("name"), "status": states[0] if states else "passed",
                           "type": test.find(states[0]).get("type") if states else None})
    return sorted(result, key=lambda r: (r["class"], r["test"]))


def finalize(root: Path) -> dict:
    # All original source/config/production/scaffold identities must STILL agree.
    verify(root)
    result = aggregate(root)
    ids = result["cases"]
    expected = {(i, a) for i in ids for a in ARMS}
    ledger = []
    gold = [(root / "cases" / i / "raw-private.json") for i in ids]
    references = [read(p)["raw"]["test_case"]["body"] for p in gold]
    for p in sorted(root.glob("cases/*/predictions/*/dispatch.json")):
        d = read(p)
        pair = (d["id"], d["arm"])
        if pair not in expected or not d["charged_to_budget"]:
            raise ValueError("Unexpected/uncharged dispatch")
        expected.remove(pair)
        prompt = d["request"]["prompt"]
        if any(ref in prompt for ref in references):
            raise ValueError("Private gold reference entered actual prompt")
        if not (p.parent / "completion.json").exists():
            raise ValueError("Charged cell incomplete")
        ledger.append({"id": pair[0], "arm": pair[1], "dispatch_sha256": file_sha256(p),
                       "completion_sha256": file_sha256(p.parent / "completion.json")})
    if expected or len(ledger) != 20:
        raise ValueError("The requested complete twenty-cell matrix is not complete")
    failures = {}
    for row in result["paired_matrix"]:
        out = root / "cases" / row["id"] / "predictions" / row["arm"]
        if row["assembled"] and not (out / "metrics.json").exists():
            raise ValueError("Assembled cell lacks evaluation")
        if row["assembled"]:
            metrics = read(out / "metrics.json")
            if len(metrics["outcomes"]) != 2:
                raise ValueError("Exactly two fresh evaluations required")
            signatures = [test_outcomes(out / f"coverage-{i}/evaluation/reports") for i in range(2)]
            for i, signature in enumerate(signatures):
                summary = metrics["outcomes"][i]["execution"].get("console_summary", {})
                if summary.get("tests_started", 0) > 0 and len(signature) != summary["tests_started"]:
                    raise ValueError("Per-test XML count disagrees with positive launcher execution")
            row["per_test_outcomes_first_run"] = signatures[0]
            row["per_test_outcomes_repeat_equal"] = signatures[0] == signatures[1] if signatures[0] else None
            row["positive_execution_repeat_stable"] = bool(row["positive_nonaborted_execution"] and row["repeat_stable"] and row["per_test_outcomes_repeat_equal"])
            for attempt in metrics["outcomes"]:
                if attempt["status"] != "passed" and attempt["coverage"] is not None:
                    raise ValueError("Failed class received primary coverage")
            if row["coverage"]:
                for scope in ["method", "class"]:
                    for counter in ["line", "branch"]:
                        actual = row["coverage"][scope]["counters"][counter]
                        reference = result["reference_coverage"][row["id"]][scope]["counters"][counter]
                        if actual["total"] != reference["total"]:
                            raise ValueError("Production denominator changed")
            row["failure_category"] = metrics["statuses"][0] if not metrics["class_pass"] else "passed"
            if not metrics["class_pass"]:
                log = out / "coverage-0/evaluation/compile.log"
                if metrics["statuses"][0] == "compile_failure" and log.exists():
                    row["failure_detail"] = log.read_text()[-2000:]
        else:
            error = (row.get("failure") or {}).get("error", "")
            row["failure_category"] = "body_java_syntax_rejection" if "balanced Java statements" in error else "schema_or_protocol_rejection"
            row["failure_detail"] = error
            row["per_test_outcomes_first_run"] = []
            row["per_test_outcomes_repeat_equal"] = None
            row["positive_execution_repeat_stable"] = False
        failures.setdefault(row["arm"], {})[row["id"]] = row["failure_category"]
        server_path = out / "server_response.json"
        server = read(server_path) if server_path.exists() else {}
        row["prompt_processing_seconds"] = server["prompt_eval_duration"] / 1e9 if "prompt_eval_duration" in server else None
        # Raw invalid/model outputs stay in the ignored run, not this compact report.
        row.pop("failure", None)
    for arm in ARMS:
        rs = [r for r in result["paired_matrix"] if r["arm"] == arm]
        result["arms"][arm]["positive_execution_repeat_stable"] = {
            "count": sum(r["positive_execution_repeat_stable"] for r in rs),
            "denominator_positive_executed": sum(r["positive_nonaborted_execution"] for r in rs)}
        for scope in ["method", "class"]:
            for counter in ["line", "branch"]:
                if any(r["class_pass"] and r["coverage"] is None for r in rs):
                    metrics = result["arms"][arm]["coverage"][scope][counter]
                    metrics["all_attempt_success_credit_pooled_ratio"] = None
                    metrics["all_attempt_success_credit_case_macro"] = None
                    metrics["credit_unavailable_reason"] = "passing_class_missing_instrumentation"
    result["failure_categories"] = failures
    result["ledger"] = ledger
    result["proof"] = {"all_twenty_unique_cells_charged_completed": True, "original_frozen_source_files_unchanged": True,
                       "gold_absent_actual_dispatch_prompts": True, "coverage_denominators_match_reference_production": True,
                       "reference_classes_passing_and_focal_invoked": all(c and c["focal_invoked"] for c in result["reference_coverage"].values()),
                       "report_helper_sha256": file_sha256(Path(__file__)), "freeze_sha256": file_sha256(root / "freeze.json"),
                       "environment_sha256": file_sha256(root / "environment.json")}
    result["model_load"] = read(root / "ft_load.json")
    hf = read(root / "hf_identity.json")
    ollama = read(root / "ollama_identity.json")
    digests = {read(p)["experiment_record"]["generation_model_digest"]
               for p in root.glob("cases/*/predictions/*/received.json")
               if "experiment_record" in read(p)}
    if len(digests) != 1:
        raise ValueError("Ollama comparison arms did not preserve one generation digest")
    result["model_identities"] = {"ollama_model": "qwen2.5-coder:7b", "ollama_digest": next(iter(digests)),
        "ollama_details": ollama["details"], "ollama_identity_sha256": file_sha256(root / "ollama_identity.json"),
        "ft_model": hf["model"], "ft_inference": hf["inference"],
        "ft_file_identities": {Path(p).name: pin for p, pin in hf["files"].items()},
        "ft_completed_steps": 300, "ft_completed_epochs": 0.6}
    result["index_manifests"] = read(root / "index_identity.json")
    result["selection_scope"] = read(root / "screening_scope.json")
    result["selection_exclusions"] = read(root / "selection.json")["exclusions"]
    result["cross_source_repository_check"] = read(root / "repository_identity_supplement.json")
    result["harness_controls"] = {name: read(root / "controls" / name / "result.json")["status"] for name in ["pass", "fail", "empty"]}
    result["demo"] = {"status": read(root / "demo/evaluation/result.json")["status"], "tests_started": 2}
    result["environment"] = {k: v for k, v in read(root / "environment.json").items() if k != "protected_files"}
    result["identity_hashing_timing"] = {"seconds": None, "reason": "freeze hashing was not separately timed; not included in generation timings"}
    result["limitations"] = ["Five convenience-filtered extracted methods from four projects; official EVAL/pilot_validation, not final TEST.",
        "Today snapshot absence verified; historic train bytes/base pretraining unknown.",
        "HF PEFT NF4 raw instruction vs Ollama Q4 schema-constrained generate: systems comparison, not isolated FT effect.",
        "Known retrieval limitations unchanged; no index rebuild, no training, no retries or repairs.",
        "Coverage is execution evidence, not semantic assertion quality or real fault detection; no buggy revisions or mutation analysis.",
        "Lexical assertion presence only; local reviewed execution is not an OS sandbox.",
        "Class metrics are extracted wrapper, including constructor/static initialization; method metrics are focal scope."]
    write_json(root / "reports/aggregate.json", result)
    write_json(Path("docs/experiments/methods2test_eval_five_v1_results.json"), result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
    validate_evaluation_run_id(a.run_id)
    root = (Path("artifacts/evaluation/runs") / a.run_id).resolve()
    result = finalize(root)
    for name, arm in result["arms"].items():
        print(name, "calls", arm["actual_calls"], "compiled", arm["compiled"]["count"], "pass", arm["class_pass"]["count"], "focal", arm["focal_invoked_accepted"]["count"],
              "line", arm["coverage"]["method"]["line"], "branch", arm["coverage"]["method"]["branch"])


if __name__ == "__main__":
    main()
