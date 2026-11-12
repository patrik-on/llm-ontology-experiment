"""One synthetic format-validation case; compose existing generators/Jupiter evaluator.

Not a benchmark, no real buggy revision, no index write, no repairs/retries.
Local execution requires explicit code review; this is NOT an OS sandbox.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_ontology.benchmarks.defects4j import load_config, require_wsl
from llm_ontology.benchmarks.defects4j_execution import (
    clean_env, evaluate_revision, file_sha256, run_process, write_json,
)
from llm_ontology.benchmarks.defects4j_runner import (
    ARMS, build_dependency_identity, generate_ft, generate_rag, generation_failure_payload,
)
from llm_ontology.core.config import read_yaml
from llm_ontology.evaluation.run_layout import require_canonical_evaluation_path
from llm_ontology.inference.experiment_runner import ExperimentCase
from llm_ontology.inference.prompting.testing_full_class_v2 import (
    DEMO_PRODUCTION, DEMO_TEST, PROFILE, PROTOCOL, apply_profile, profile_identity,
)
from llm_ontology.ingestion.manifest import DatasetManifest

# Evaluator-only control. Never included in case, instruction, query or retrieval corpus.
GOLD_CONTROL = """package validation.batches;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
public class BatchSizerControl {
    @Test void roundsAndSupportsLargeCounts() {
        assertEquals(0, BatchSizer.groupsNeeded(0, 7));
        assertEquals(3, BatchSizer.groupsNeeded(12, 4));
        assertEquals(4, BatchSizer.groupsNeeded(13, 4));
        assertEquals(1073741824, BatchSizer.groupsNeeded(Integer.MAX_VALUE, 2));
    }
    @Test void rejectsInvalidArguments() {
        assertThrows(IllegalArgumentException.class, () -> BatchSizer.groupsNeeded(-1, 3));
        assertThrows(IllegalArgumentException.class, () -> BatchSizer.groupsNeeded(3, 0));
        assertThrows(IllegalArgumentException.class, () -> BatchSizer.groupsNeeded(3, -1));
    }
}
"""


def load_protocol(path: Path):
    raw = read_yaml(path)
    if raw["protocol"] != PROTOCOL or raw["prompt_profile"] != PROFILE or raw["max_new_tokens"] != 4096:
        raise ValueError("Explicit v2 profile/protocol and shared 4096-token limit required.")
    runtime = load_config(Path(raw["runtime_config"]))
    runtime = runtime.model_copy(update={"max_new_tokens": 4096})
    manifest = DatasetManifest.model_validate_json(Path(raw["manifest"]).read_text())
    if manifest.usage_role.value != "validation" or manifest.allowed_for_indexing:
        raise ValueError("Fixture must be validation-only and non-indexable.")
    manifest.require_source_matches()
    if manifest.source_path != raw["fixture"] or manifest.case_count != 1:
        raise ValueError("Expected exactly the declared independent fixture.")
    return raw, runtime, manifest


def fixture_case(source: str) -> ExperimentCase:
    return ExperimentCase(case_id="synthetic-batch-sizer-v2", instruction="", input_text=source,
        structured_identity={"class_name": "validation.batches.BatchSizer", "method_name": "groupsNeeded", "focal_method": "groupsNeeded"},
        metadata={"protocol": PROTOCOL, "dataset_version": "synthetic-format-validation-v2",
                  "usage_role": "validation", "allowed_for_indexing": False,
                  "scientific_benchmark": False})


def identity(path: Path, raw: dict, runtime) -> dict:
    return {"config_sha256": file_sha256(path), "runtime_config_sha256": file_sha256(Path(raw["runtime_config"])),
            "sources": build_dependency_identity(runtime), "fixture_sha256": file_sha256(Path(raw["fixture"])),
            "manifest_sha256": file_sha256(Path(raw["manifest"])), "profile": profile_identity(),
            "java_sha256": file_sha256(runtime.java_home / "bin/java"),
            "javac_sha256": file_sha256(runtime.java_home / "bin/javac"),
            "junit_sha256": file_sha256(runtime.junit_jar)}


def compile_production(source: str, name: str, output: Path, runtime) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    java_file = output / (name + ".java")
    java_file.write_text(source, encoding="utf-8")
    binary = output / "classes"
    binary.mkdir()
    result = run_process([str(runtime.java_home / "bin/javac"), "-encoding", "UTF-8", "-proc:none",
                          "-d", str(binary), str(java_file)], output,
                         clean_env(output / "home", runtime.java_home), 30, output / "compile.log")
    write_json(output / "compile.json", result)
    if result["status"] != "completed" or result["returncode"] != 0:
        raise RuntimeError("Reviewed synthetic production compilation failed.")
    return {"bin_classes": str(binary), "dependencies": [], "source_sha256": file_sha256(java_file),
            "binaries": {str(p): file_sha256(p) for p in binary.rglob("*.class")}}


def evaluate(source: str, revision: dict, output: Path, runtime) -> dict:
    return evaluate_revision(source, revision, output=output, java_home=runtime.java_home,
        junit_jar=runtime.junit_jar, junit_sha256=runtime.junit_sha256, timeout=30)


def verify_prepared(root: Path, pins: dict) -> dict:
    if file_sha256(root / "prepared.json") != pins["prepared_sha256"]:
        raise ValueError("Prepared fixture/control evidence changed.")
    prepared = json.loads((root / "prepared.json").read_text())
    for path, digest in prepared["revision"]["binaries"].items():
        if file_sha256(Path(path)) != digest:
            raise ValueError("Production binary changed.")
    if not prepared["controls_passed"]:
        raise ValueError("Demonstration and evaluator controls must pass before generation.")
    return prepared


def generation_observation(generated: dict, arm: str) -> dict:
    if arm == "ft_testing":
        data = generated["generation"]
        return {"input_tokens": data.get("input_tokens"), "output_tokens": data.get("output_tokens"),
                "finish_reason": data.get("finish_reason"), "truncated": data.get("output_truncated")}
    record = generated["experiment_record"]
    data = record["structured_output_attempts"][0]["generation_metadata"]
    return {"input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count"),
            "finish_reason": data.get("done_reason"), "truncated": data.get("done_reason") == "length",
            "prompt_budget": record.get("prompt_budget", record.get("evaluation", {}))}


def summarize(root: Path) -> dict:
    arms = {}
    for arm in ARMS:
        out = root / "predictions" / arm
        gen = out / "generation.json"
        metrics = root / "metrics" / arm / "result.json"
        failure = out / "failure.json"
        generated = json.loads(gen.read_text()) if gen.exists() else None
        result = json.loads(metrics.read_text()) if metrics.exists() else {}
        observation = generation_observation(generated, arm) if generated else {}
        accepted = bool(result.get("status") == "passed" and
                        2 <= result.get("discovery", {}).get("executed", 0) <= 4 and
                        observation.get("truncated") is False and
                        observation.get("finish_reason") in {"eos", "stop"})
        arms[arm] = {"planned": 1, "attempted": int(out.exists()), "generated": int(gen.exists()),
            "status": result.get("status", "generation_failure" if failure.exists() else "not_evaluated"),
            "executed": result.get("discovery", {}).get("executed", 0), "accepted": accepted,
            "generation": observation}
    return {"protocol": PROTOCOL, "prompt_profile": PROFILE, "planned_cases": 1, "planned_arms": 3,
            "arms": arms, "scientific_scores": False, "bug_detection": "not_applicable_no_buggy_revision",
            "comparison": "new fixture/profile; no comparable baseline or causal improvement claim",
            "index_contamination": "unknown_unchanged_existing_index", "diagnostic_only": True,
            "sandbox": "none-reviewed-local-execution"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "generate", "evaluate", "report"])
    parser.add_argument("--config", type=Path, default=Path("configs/benchmarks/testing_format_validation_v2.yaml"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--reviewed-local-execution", action="store_true")
    args = parser.parse_args(argv)
    require_wsl()
    raw, runtime, manifest = load_protocol(args.config)
    from llm_ontology.evaluation.run_layout import validate_evaluation_run_id
    validate_evaluation_run_id(args.run_id)
    root = require_canonical_evaluation_path(Path("artifacts/evaluation/runs") / args.run_id).resolve()
    if args.action in {"prepare", "evaluate"} and not args.reviewed_local_execution:
        raise ValueError("Review production/demo/generated code first; --reviewed-local-execution required.")
    current = identity(args.config, raw, runtime)
    pin_path = root / "protocol_identity.json"
    if args.action == "prepare":
        root.mkdir(parents=True, exist_ok=False)
        write_json(pin_path, current)
        write_json(root / "fixture_manifest.json", manifest.model_dump(mode="json"))
        source = Path(raw["fixture"]).read_text()
        revision = compile_production(source, "BatchSizer", root / "production", runtime)
        demo = compile_production(DEMO_PRODUCTION, "Labels", root / "demo-production", runtime)
        demo_result = evaluate(DEMO_TEST, demo, root / "controls/demo", runtime)
        gold = evaluate(GOLD_CONTROL, revision, root / "controls/fixture", runtime)
        empty = evaluate("class EmptyTest {}", revision, root / "controls/empty", runtime)
        negative = evaluate("import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; "
                            "class NegativeTest { @Test void t() { assertTrue(false); } }",
                            revision, root / "controls/negative", runtime)
        passed = (demo_result["status"] == gold["status"] == "passed" and
                  demo_result["discovery"]["executed"] == gold["discovery"]["executed"] == 2 and
                  empty["status"] == "no_tests" and negative["status"] == "assertion_failure")
        case = fixture_case(source)
        write_json(root / "case.json", case.model_dump(mode="json"))
        prepared = {"revision": revision, "controls_passed": passed, "demo": demo_result,
                    "fixture_control": gold, "empty": empty, "negative": negative,
                    "case_sha256": file_sha256(root / "case.json")}
        write_json(root / "prepared.json", prepared)
        write_json(root / "prepared_identity.json", {"prepared_sha256": file_sha256(root / "prepared.json")})
        print(json.dumps({"controls_passed": passed, "root": str(root)}))
        return 0 if passed else 2
    if json.loads(pin_path.read_text()) != current:
        raise ValueError("Source/config/toolchain/fixture identity changed: use a new run ID.")
    prepared = verify_prepared(root, json.loads((root / "prepared_identity.json").read_text()))
    if file_sha256(root / "case.json") != prepared["case_sha256"]:
        raise ValueError("Validation case changed.")
    if args.action == "report":
        report = summarize(root)
        write_json(root / "reports/summary.json", report)
        print(json.dumps(report, indent=2))
        return 0
    if args.arm is None:
        raise ValueError("--arm is required.")
    out = root / "predictions" / args.arm
    if args.action == "generate":
        if not args.diagnostic:
            raise ValueError("Only --diagnostic generation is enabled.")
        # Exclusive per-arm attempt directory: max one call/arm, including failures.
        out.mkdir(parents=True, exist_ok=False)
        case = apply_profile(ExperimentCase.model_validate_json((root / "case.json").read_text()),
                             envelope="ft" if args.arm == "ft_testing" else "rag")
        write_json(out / "case_with_profile.json", case.model_dump(mode="json"))
        try:
            generated = (generate_ft(runtime, case, out) if args.arm == "ft_testing" else
                         generate_rag(runtime, case, out, args.arm,
                                      {"scientifically_clean": False, "diagnostic_only": True,
                                       "index_contamination": "unknown_unchanged_existing_index"}))
            (out / "generated.java").write_text(generated["source"], encoding="utf-8")
            generated.update({"source_sha256": file_sha256(out / "generated.java"),
                              "profile_identity": profile_identity(), "protocol": PROTOCOL})
            write_json(out / "generation.json", generated)
            if args.arm != "ft_testing":
                attempts = generated["experiment_record"]["structured_output_attempts"]
                (out / "raw.txt").write_text(attempts[0]["raw_response"], encoding="utf-8")
            print(json.dumps({"arm": args.arm, **generation_observation(generated, args.arm)}))
        except Exception as exc:
            write_json(out / "failure.json", generation_failure_payload(
                exc, case_sha256=prepared["case_sha256"], arm=args.arm))
            raise
        return 0
    generated = json.loads((out / "generation.json").read_text())
    if file_sha256(out / "generated.java") != generated["source_sha256"]:
        raise ValueError("Generated source changed; repairs forbidden.")
    result = evaluate((out / "generated.java").read_text(), prepared["revision"],
                      root / "metrics" / args.arm, runtime)
    print(json.dumps({"arm": args.arm, "status": result["status"],
                      "executed": result.get("discovery", {}).get("executed", 0)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
